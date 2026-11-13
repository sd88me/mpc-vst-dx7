// Dexed (DX7) 2.0: the MPC plugin front end (framework/mpc_plugin.h) around the unchanged 1.x engine.
//
// Signal flow: MPC MIDI -> engine on_midi (split at each event's sample offset) -> engine render_block (int16
// stereo) -> float outputs. The engine is src/dsp/dx7_plugin.cpp (schwung-dx7 / Dexed / MSFA, GPL-3.0), driven
// through its own plugin_api_v2 functions, which are compiled into this file.
//
// Parameters: 228, generated from module.json in params.lock order (tools/gen_params.py), so every index is the
// same as in 1.x. Three kinds:
//   * value params (algorithm, op1_level ...): a change is applied to the engine on the audio thread, as the
//     engine's own set_param string ("12").
//   * momentary params (next_syx_bank, bank_slot_3 ...): 0 -> 1 fires the engine verb once, then the param drops
//     back to 0.
//   * text params (bank_name, patch_name ...): the value is unused; the screen shows the engine's text for them
//     (formatValue -> get_param).
// After a patch or bank change the engine's new values are read back into the parameters (resync).
//
// Parameter 0 is "preset" (frozen order). The MPC nudges parameter 0 to 0/1 and back on every prepare, so preset
// changes are applied only after the value has been stable for ~50 ms (a nudge-and-return never loads a patch).
//
// Threads: the audio thread never does file I/O or host calls. A bank change (next/prev, a tile, the bank index) is
// queued to a worker thread that reads the bank file ahead; the audio thread applies the change a few ms later, when
// the file is ready (the engine's v2_load_syx then takes the bytes from the prefetch slot). The worker also writes
// favourites.dat and makes the host display-update calls. A project's saved bank is read ahead on the UI thread.
//
// State: the framework saves every parameter by id; the engine's own "state" JSON (bank by name, all voice
// params) goes in the extra state and is applied last, on the audio thread.

#include "mpc_plugin.h"
#include "mpc_resources.h"

#include "dsp/dx7_plugin.cpp"
#include "params_gen.h"
#include "algo_carriers.h"

#include <atomic>
#include <chrono>
#include <random>
#include <thread>
#include <string>
#include <vector>
#include <sys/stat.h>

namespace {

// A test build installs next to the release with its own identity: ./build-sdk.sh beta.
#ifndef DEXED_NAME
#define DEXED_NAME "Dexed (DX7)"
#endif
#ifndef DEXED_UID
#define DEXED_UID 'F', 'D', 'X', '2'
#endif
#define DEXED_FOURCC(...) MPC_FOURCC(__VA_ARGS__)   // expands DEXED_UID before MPC_FOURCC counts its arguments
const uint32_t kUid = DEXED_FOURCC(DEXED_UID);

mpc::PluginInfo makeInfo()
{
    mpc::PluginInfo i;
    i.name = DEXED_NAME;
    i.vendor = "sd88me";
    i.uniqueId = kUid;
    i.version = 2000;
    i.isInstrument = true;
    i.numInputs = 0;
    i.numOutputs = 2;
    return i;
}

bool isDir(const std::string& p)
{
    struct stat st;
    return stat(p.c_str(), &st) == 0 && S_ISDIR(st.st_mode);
}

// Engine verbs that change the loaded patch or bank: after them the parameters are re-read from the engine.
bool changesPatch(const char* key)
{
    return !strcmp(key, "preset") || !strcmp(key, "syx_bank_index") || !strcmp(key, "next_syx_bank") ||
           !strcmp(key, "prev_syx_bank") || !strcmp(key, "preset_next") || !strcmp(key, "preset_prev") ||
           !strncmp(key, "bank_slot_", 10) || !strncmp(key, "patch_slot_", 11) || !strcmp(key, "state") ||
           !strcmp(key, "bank_page_next") || !strcmp(key, "bank_page_prev");   // page flips change the CARTS tile names
}

// A tiny lock between the UI thread (reading engine text) and the audio thread (changing the engine).
// The audio thread only ever try-locks: if the UI holds it, the changes wait for the next block.
struct EngineLock
{
    std::atomic_flag f = ATOMIC_FLAG_INIT;
    bool tryLock() { return !f.test_and_set(std::memory_order_acquire); }
    void lock() { while (f.test_and_set(std::memory_order_acquire)) {} }
    void unlock() { f.clear(std::memory_order_release); }
};

} // namespace

class DexedPlugin : public mpc::Plugin
{
public:
    DexedPlugin() : mpc::Plugin(makeInfo())
    {
        const auto& t = paramSpecs();
        for (const ParamSpec& s : t)
        {
            if (s.kind == ParamSpec::Choice)
                addParam(mpc::choiceParam(s.key, s.name, s.choices, s.def));
            else
                addParam(mpc::intParam(s.key, s.name, s.min, s.max, s.def));
        }
        // Programs = the MPC's PRESET menu. 0 is "the cart patch" (picking it does nothing); 1..64 are favourite slots,
        // renamed as favourites are saved and deleted (the framework's program list is fixed at load, names are not).
        addProgram("Cart patch", {});
        for (int i = 0; i < kFavSlots; ++i) addProgram("--", {});
        dirty_ = new std::atomic<bool>[t.size()];
        for (size_t i = 0; i < t.size(); ++i) if (!strcmp(t[i].key, "syx_bank_index")) bankIdx_ = (int)i;
        hostAt_ = new std::atomic<long long>[t.size()];
        for (size_t i = 0; i < t.size(); ++i) { dirty_[i].store(false); hostAt_[i].store(0); }

        // Carts, first match wins:
        //   <plugin folder>/dx7_carts  - a 1.x install upgraded in place (1.x keeps its carts there, next to the .so)
        //   /sdcard/vst/dx7_carts      - older 1.x installs
        //   <plugin folder>/Content/carts - a fresh 2.0 install
        // (Not mpc::contentPath(): its function-local static std::string crashes on dlclose in the zig/libc++ build.)
        const std::string folder = mpc::detail::computePluginFolder();
        if (isDir(folder + "/dx7_carts")) cartDir_ = folder + "/dx7_carts";
        else if (isDir("/sdcard/vst/dx7_carts")) cartDir_ = "/sdcard/vst/dx7_carts";
        else cartDir_ = folder + "/Content/carts";
        favPath_ = folder + "/favourites.dat";
        moveIdx_ = findParam("move");
        loadFavourites();
        inst_ = v2_create_instance(cartDir_.c_str(), "{}");
        syncFromEngine();
        worker_ = std::thread(&DexedPlugin::workerMain, this);
    }

    ~DexedPlugin() override
    {
        quit_.store(true);
        if (worker_.joinable()) worker_.join();
        if (inst_) v2_destroy_instance(inst_);
        delete[] dirty_;
        delete[] hostAt_;
    }

    void prepare(double, int) override {}

    // Runs on the audio thread after a state load (and on resume): apply the engine state saved with the project.
    void reset() override
    {
        int prog = currentProgram();
        if (prog != lastProgram_)
        {
            lastProgram_ = prog;
            if (prog > 0 && !ignoreProgram_ && inst_) loadFavourite(prog - 1);
        }
        ignoreProgram_ = false;
        if (!pendingState_.empty() && inst_)
        {
            lock_.lock();
            v2_set_param(inst_, "state", pendingState_.c_str());
            lock_.unlock();
            pendingState_.clear();
            presetCountdown_ = -1;
            // The engine state chose the bank and patch; the saved parameter values then win (they are the
            // project's edits, and some, such as operator on/off, are not part of the engine's state JSON).
            pushAllToEngine();
        }
    }

    void parameterChanged(int index, float plain) override
    {
        const ParamSpec& s = paramSpecs()[(size_t)index];
        // Momentary first: bank_slot_N / patch_slot_N are verbs that also show text (a tile with a name).
        if (s.flags & kMomentary) { if (plain < 0.5f) return; }
        else if (s.flags & kText) return;
        hostAt_[index].store(nowMs(), std::memory_order_relaxed);
        if (index == bankIdx_ && bankPushing_.load()) return;   // the host echoing the cart the worker just gave it
        if (index == bankIdx_ && inst_) bankMove((int)std::lround(plain));
        dirty_[index].store(true, std::memory_order_release);
    }

    static long long nowMs()
    {
        return std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();
    }

    bool formatValue(int index, float plain, std::string& out) override
    {
        const ParamSpec& s = paramSpecs()[(size_t)index];
        if (!strcmp(s.key, "syx_bank_index") && inst_)   // the value text of the bank knob/slider is the cart name
        {
            dx7_instance_t* d = (dx7_instance_t*)inst_;
            int k = (int)std::lround(plain);
            if (d->syx_banks && k >= 0 && k < d->syx_bank_count) { out = d->syx_banks[k].name; return true; }
            return false;
        }
        if (!(s.flags & kText) || !inst_) return false;
        (void)plain;
        if (!strcmp(s.key, "fav_text"))
        {
            int n = 0;
            favLock_.lock();
            for (const Fav& f : favs_) n += f.used ? 1 : 0;
            favLock_.unlock();
            out = std::to_string(n) + " / " + std::to_string(kFavSlots) + " SAVED";
            return true;
        }
        char buf[256] = "";
        lock_.lock();
        v2_get_param(inst_, s.key, buf, sizeof(buf));
        lock_.unlock();
        out = buf;
        return true;
    }

    void saveExtraState(std::vector<uint8_t>& out) override
    {
        if (!inst_) return;
        std::vector<char> buf(64 * 1024);
        lock_.lock();
        int n = v2_get_param(inst_, "state", buf.data(), (int)buf.size());
        lock_.unlock();
        if (n > 0 && n < (int)buf.size()) out.assign(buf.data(), buf.data() + n);
    }

    void loadExtraState(const uint8_t* data, size_t size) override
    {
        pendingState_.assign(reinterpret_cast<const char*>(data), size);   // applied in reset(), on the audio thread
        ignoreProgram_ = true;
        char path[600]; int sub;   // read the project's bank here on the UI thread, so reset() does no file I/O
        if (inst_ && dx7_bank_target((dx7_instance_t*)inst_, "state", pendingState_.c_str(), path, sizeof(path), &sub) == 0)
            dx7_prefetch_bank((dx7_instance_t*)inst_, path, sub);
    }

    void process(mpc::ProcessContext& ctx) override
    {
        if (!inst_) return;
        applyParamChanges(ctx.numFrames);

        // The engine only renders whole N-sample (64) blocks: asked for fewer, it still advances every voice by N and
        // drops the rest, so a partial block is a jump in the waveform (a click). 1.x always rendered 128-frame blocks.
        // So render N at a time into pcm_ and hand it out across host blocks; MIDI lands on the next N boundary (<1.5 ms).
        float* outL = ctx.outputs[0];
        float* outR = ctx.numOutputs > 1 ? ctx.outputs[1] : nullptr;
        int mi = 0;
        for (int frame = 0; frame < ctx.numFrames; ++frame)
        {
            if (pcmPos_ >= N)
            {
                while (mi < ctx.numMidiEvents && ctx.midi[mi].sampleOffset <= frame)
                {
                    const mpc::MidiEvent& e = ctx.midi[mi++];
                    v2_on_midi(inst_, e.data, e.size, MOVE_MIDI_SOURCE_EXTERNAL);
                }
                v2_render_block(inst_, pcm_, N);
                pcmPos_ = 0;
            }
            outL[frame] = pcm_[2 * pcmPos_] * (1.0f / 32768.0f);
            if (outR) outR[frame] = pcm_[2 * pcmPos_ + 1] * (1.0f / 32768.0f);
            ++pcmPos_;
        }
        while (mi < ctx.numMidiEvents)   // events not yet due at a block boundary: apply now, heard from the next block
        {
            const mpc::MidiEvent& e = ctx.midi[mi++];
            v2_on_midi(inst_, e.data, e.size, MOVE_MIDI_SOURCE_EXTERNAL);
        }
    }

private:
    static constexpr int kFavSlots = 64;
    // The bank index param spans 0..8191, but the cart list is far shorter. A Q-Link or data-wheel tick moves it ~64 (1/128) and a
    // finger drag by thousands, so an absolute reading would skip carts or run past the end. Every host-driven change is therefore
    // RELATIVE: one cart per change, in the direction of the move (taps and tiles use the verbs, not this). The engine wraps past either end.
    // Each host move is counted as one step in parameterChanged (bankMove), in the direction the host's value moved: from its
    // previous value (bankHost_) or from the cart, whichever is the smaller move. While a control turns the read-back waits 300 ms,
    // so the host's value runs ahead of the cart, and after a read-back some controls go on from their own old value: measured
    // against the cart alone, turning back stepped the wrong way. Counting there, not here, also keeps every click: the audio thread
    // sees one dirty flag per block, and several clicks in one block, or during a cart's file read, used to become one step.
    // bankValue (audio thread) adds the counted steps to the cart being gone to (bankTarget_) and returns it; the engine's wrap rule.
    int bankValue(bool take = true)   // take: add the counted steps (not when applying a cart whose file is already read)
    {
        dx7_instance_t* d = (dx7_instance_t*)inst_;
        const int n = d->syx_bank_count, cur = d->syx_bank_index;
        if (n <= 0) return cur;
        int t = bankTarget_.load();
        if (t < 0) t = cur;
        const int k = take ? bankSteps_.exchange(0) : 0;
        if (k) t = ((t + k) % n + n) % n;
        bankTarget_.store(t);
        return t;
    }
    void bankMove(int v)   // parameterChanged: one host move of the cart value
    {
        dx7_instance_t* d = (dx7_instance_t*)inst_;
        const int h = bankHost_.exchange(v);
        int c = bankTarget_.load();
        if (c < 0) c = d->syx_bank_index;
        const int dH = h >= 0 ? v - h : 0, dV = v - c;
        const int m = (dH != 0 && (dV == 0 || std::abs(dH) < std::abs(dV))) ? dH : dV;
        if (m) bankSteps_.fetch_add(m > 0 ? 1 : -1);
        if (v <= (int)param(bankIdx_).min || v >= (int)param(bankIdx_).max) bankPin_.store(true);
    }
    std::atomic<int> bankHost_{-1}, bankTarget_{-1}, bankSteps_{0};   // host's last value, cart being gone to, steps not yet applied
    int bankIdx_ = -1;
    std::atomic<bool> bankPin_{false}, bankPushing_{false};

    // ---- favourites: a whole voice (156-byte unpacked DX7 voice, with the user's edits) per slot ----------------
    struct Fav { bool used = false; uint8_t voice[DX7_PATCH_SIZE] = {}; char name[11] = {}; };
    // file: "DXF1" | u32 slots | per slot: u8 used, 156 voice bytes, 10 name bytes

    void loadFavourites()
    {
        favs_.assign(kFavSlots, Fav());
        FILE* f = fopen(favPath_.c_str(), "rb");
        if (!f) return;
        char magic[4]; uint32_t n = 0;
        if (fread(magic, 1, 4, f) == 4 && !memcmp(magic, "DXF1", 4) && fread(&n, 4, 1, f) == 1)
            for (uint32_t i = 0; i < n && i < (uint32_t)kFavSlots; ++i)
            {
                uint8_t used = 0;
                if (fread(&used, 1, 1, f) != 1 || fread(favs_[i].voice, 1, DX7_PATCH_SIZE, f) != DX7_PATCH_SIZE ||
                    fread(favs_[i].name, 1, 10, f) != 10) break;
                favs_[i].used = used != 0;
            }
        fclose(f);
        for (int i = 0; i < kFavSlots; ++i) nameProgram(i);
    }

    void writeFavourites()   // worker thread: a snapshot under the lock, then the file
    {
        std::vector<Fav> snap;
        favLock_.lock();
        snap = favs_;
        favLock_.unlock();
        std::string tmp = favPath_ + ".tmp";
        FILE* f = fopen(tmp.c_str(), "wb");
        if (!f) return;
        uint32_t n = kFavSlots;
        fwrite("DXF1", 1, 4, f); fwrite(&n, 4, 1, f);
        for (const Fav& v : snap) { uint8_t u = v.used; fwrite(&u, 1, 1, f); fwrite(v.voice, 1, DX7_PATCH_SIZE, f); fwrite(v.name, 1, 10, f); }
        fclose(f);
        rename(tmp.c_str(), favPath_.c_str());
    }

    void nameProgram(int i)
    {
        std::string nm = "--";
        if (favs_[i].used)
        {
            nm = favs_[i].name;
            while (!nm.empty() && nm.back() == ' ') nm.pop_back();
            if (nm.empty()) nm = "Favourite";
        }
        programs_[(size_t)i + 1].name = std::to_string(i + 1) + " " + nm;
    }

    void saveFavourite()   // audio thread, engine lock held
    {
        dx7_instance_t* d = (dx7_instance_t*)inst_;
        apply_patch_params(d);   // make sure current_patch holds the live edits
        favLock_.lock();
        int slot = -1;
        for (int i = 0; i < kFavSlots && slot < 0; ++i) if (!favs_[i].used) slot = i;
        if (slot >= 0)
        {
            Fav& f = favs_[slot];
            f.used = true;
            memcpy(f.voice, d->current_patch, DX7_PATCH_SIZE);
            memcpy(f.name, d->current_patch + 145, 10);   // the DX7 voice name bytes
            f.name[10] = 0;
            nameProgram(slot);
        }
        favLock_.unlock();
        if (slot >= 0) favDirty_.store(true);
    }

    void deleteFavourite()  // deletes the favourite that is loaded now (picked from the PRESET menu)
    {
        int prog = currentProgram();
        if (prog <= 0) return;
        favLock_.lock();
        bool had = favs_[prog - 1].used;
        if (had) { favs_[prog - 1] = Fav(); nameProgram(prog - 1); }
        favLock_.unlock();
        if (had) favDirty_.store(true);
    }

    void loadFavourite(int slot)   // audio thread
    {
        if (slot < 0 || slot >= kFavSlots) return;
        Fav f;
        favLock_.lock();
        f = favs_[slot];
        favLock_.unlock();
        if (!f.used) return;
        dx7_instance_t* d = (dx7_instance_t*)inst_;
        lock_.lock();
        for (int i = 0; i < MAX_VOICES; i++) if (d->voice_note[i] >= 0 && d->voices[i]) d->voices[i]->keyup();
        memcpy(d->current_patch, f.voice, DX7_PATCH_SIZE);
        snprintf(d->patch_name, sizeof(d->patch_name), "%s", f.name);
        extract_patch_params(d);
        d->lfo.reset(d->current_patch + 137);
        lock_.unlock();
        syncFromEngine();
        displayDirty_.store(true);
    }

    // ---- worker thread -------------------------------------------------------------------------------------------
    static bool isBankVerb(const char* key)
    {
        return !strcmp(key, "syx_bank_index") || !strcmp(key, "next_syx_bank") || !strcmp(key, "prev_syx_bank") ||
               !strncmp(key, "bank_slot_", 10);
    }

    bool postJob(const char* path, int sub)   // audio thread: never waits (a busy lock just means "try next block")
    {
        if (!jobLock_.tryLock()) return false;
        snprintf(jobPath_, sizeof(jobPath_), "%s", path);
        jobSub_ = sub;
        jobSeq_.fetch_add(1, std::memory_order_release);
        jobLock_.unlock();
        return true;
    }

    void workerMain()
    {
        uint32_t seen = 0;
        while (!quit_.load(std::memory_order_relaxed))
        {
            std::this_thread::sleep_for(std::chrono::milliseconds(4));
            if (jobSeq_.load(std::memory_order_acquire) != seen)
            {
                char path[600]; int sub; uint32_t seq;
                jobLock_.lock();
                snprintf(path, sizeof(path), "%s", jobPath_);
                sub = jobSub_;
                seq = jobSeq_.load();
                jobLock_.unlock();
                dx7_prefetch_bank((dx7_instance_t*)inst_, path, sub);   // the file I/O
                seen = seq;
                readySeq_.store(seq, std::memory_order_release);
            }
            if (favDirty_.exchange(false)) writeFavourites();
            if (displayDirty_.exchange(false)) requestDisplayUpdate();
            if (bankPin_.exchange(false)) pushBankToHost();
        }
    }

    // The cart value sits at the bottom of its 0..8191 range (it is the cart number), so a turn down soon pins the host's value at 0,
    // and a pinned control sends nothing more: fast clicks down were lost. When a move lands on an end, the worker gives the host the
    // cart being gone to straight away (no 300 ms hold), so the next click has room again.
    void pushBankToHost()
    {
        dx7_instance_t* d = (dx7_instance_t*)inst_;
        int t = bankTarget_.load();
        if (t < 0) t = d->syx_bank_index;
        t += bankSteps_.load();   // steps the audio thread has not taken yet
        const int n = d->syx_bank_count;
        if (n > 0) t = (t % n + n) % n;
        bankHost_.store(t);
        store(bankIdx_, (float)t);
        bankPushing_.store(true);
        notifyHostParameterChanged(bankIdx_);
        bankPushing_.store(false);
    }

    std::thread worker_;
    std::atomic<bool> quit_{false}, displayDirty_{false}, favDirty_{false};
    EngineLock jobLock_, favLock_;
    char jobPath_[600] = "";
    int jobSub_ = 0;
    std::atomic<uint32_t> jobSeq_{0}, readySeq_{0};
    int pendingParam_ = -1, prefetchedParam_ = -1;
    std::mt19937 rng_{(unsigned)std::chrono::steady_clock::now().time_since_epoch().count()};
    int randBank_ = 0, randPatch_ = 0;
    uint32_t pendingSeq_ = 0;

    std::vector<Fav> favs_;
    std::string favPath_;
    int lastProgram_ = 0;
    bool ignoreProgram_ = false;

    void applyParamChanges(int frames)
    {
        const auto& t = paramSpecs();
        bool any = presetCountdown_ >= 0 || pendingParam_ >= 0;
        for (size_t i = 0; i < t.size() && !any; ++i) any = dirty_[i].load(std::memory_order_relaxed);
        if (!any || !lock_.tryLock()) return;

        // A bank change waiting for its file: when the worker has read it, apply it now (no file I/O left to do).
        if (pendingParam_ >= 0 && readySeq_.load(std::memory_order_acquire) == pendingSeq_)
        {
            dirty_[pendingParam_].store(true, std::memory_order_release);
            prefetchedParam_ = pendingParam_;
            pendingParam_ = -1;
        }

        bool resync = false, favChanged = false;
        char val[32];
        for (size_t i = 0; i < t.size(); ++i)
        {
            if (!dirty_[i].exchange(false, std::memory_order_acq_rel)) continue;
            const ParamSpec& s = t[i];
            if (i == 0)   // preset: debounce (see the header comment)
            {
                presetTarget_ = getInt(0);
                presetCountdown_ = (int)(0.05 * sampleRate() / std::max(1, frames)) + 1;
                continue;
            }
            if (!strcmp(s.key, "fav_save") || !strcmp(s.key, "fav_delete"))
            {
                if (s.key[4] == 's') saveFavourite(); else deleteFavourite();
                store((int)i, 0.0f);
                favChanged = true;
                continue;
            }
            if (!strcmp(s.key, "move"))
            {
                applyMove();
                continue;
            }
            if (!strcmp(s.key, "generate") || !strcmp(s.key, "mutate"))
            {
                generateVoice(s.key[0] == 'm');
                store((int)i, 0.0f);
                seedMove();      // a new voice: seed its movement, and apply the MOVE slider as it stands
                applyMove();
                moveKeep_ = true;
                resync = true;
                continue;
            }
            if (!strcmp(s.key, "rand_prog"))
            {   // a random cart AND a random patch in it: pick, have the worker read the bank, then load both
                dx7_instance_t* d = (dx7_instance_t*)inst_;
                if ((int)i != prefetchedParam_)
                {
                    int n = d->syx_bank_count;
                    if (n > 0)
                    {
                        randBank_ = (int)(rng_() % (unsigned)n);
                        if (n > 1 && randBank_ == d->syx_bank_index) randBank_ = (randBank_ + 1 + (int)(rng_() % (unsigned)(n - 1))) % n;
                        randPatch_ = (int)(rng_() % 32u);
                        char path[600]; int sub;
                        snprintf(val, sizeof(val), "%d", randBank_);
                        if (dx7_bank_target(d, "syx_bank_index", val, path, sizeof(path), &sub) == 0)
                        {
                            if (postJob(path, sub)) { pendingParam_ = (int)i; pendingSeq_ = jobSeq_.load(); }
                            else dirty_[i].store(true, std::memory_order_release);
                            continue;
                        }
                    }
                    store((int)i, 0.0f);   // no carts: nothing to pick
                    continue;
                }
                prefetchedParam_ = -1;   // the bank file is read: apply
                snprintf(val, sizeof(val), "%d", randBank_);
                v2_set_param(inst_, "syx_bank_index", val);
                snprintf(val, sizeof(val), "%d", randPatch_);
                v2_set_param(inst_, "preset", val);
                store((int)i, 0.0f);
                resync = true;
                continue;
            }
            if (!strcmp(s.key, "preset_next") || !strcmp(s.key, "preset_prev"))
            {   // step the patch within the loaded bank (wraps); the LCD arrows use these
                dx7_instance_t* d = (dx7_instance_t*)inst_;
                int n = d->preset_count > 0 ? d->preset_count : 32;
                int nx = (d->current_preset + (s.key[7] == 'n' ? 1 : -1) + n) % n;
                snprintf(val, sizeof(val), "%d", nx);
                v2_set_param(inst_, "preset", val);
                store((int)i, 0.0f);
                resync = true;
                continue;
            }
            if (isBankVerb(s.key) && (int)i != prefetchedParam_)
            {   // queue the file read on the worker, apply when it is ready (the newest request replaces an older one)
                if (s.flags & kMomentary) snprintf(val, sizeof(val), "1");
                else snprintf(val, sizeof(val), "%d", !strcmp(s.key, "syx_bank_index") ? bankValue() : getInt((int)i));
                char path[600]; int sub;
                if (dx7_bank_target((dx7_instance_t*)inst_, s.key, val, path, sizeof(path), &sub) == 0)
                {
                    if (postJob(path, sub)) { pendingParam_ = (int)i; pendingSeq_ = jobSeq_.load(); }
                    else dirty_[i].store(true, std::memory_order_release);   // the worker was reading the job: retry next block
                    continue;
                }
            }
            if ((int)i == prefetchedParam_) prefetchedParam_ = -1;
            if (s.flags & kMomentary)
            {
                v2_set_param(inst_, s.key, "1");
                store((int)i, 0.0f);
            }
            else
            {
                // the read cart, as it was asked for: steps counted since then set the param dirty again and start the next read
                snprintf(val, sizeof(val), "%d", (int)i == bankIdx_ ? bankValue(false) : getInt((int)i));
                v2_set_param(inst_, s.key, val);
                if ((int)i == bankIdx_ && bankSteps_.load() == 0 &&
                    bankTarget_.load() == ((dx7_instance_t*)inst_)->syx_bank_index)
                    bankTarget_.store(-1);   // arrived: the next move starts from the cart again
            }
            if (changesPatch(s.key)) resync = true;
        }
        if (presetCountdown_ >= 0 && --presetCountdown_ < 0)
        {
            if (getInt(0) == presetTarget_)
            {
                snprintf(val, sizeof(val), "%d", presetTarget_);
                v2_set_param(inst_, "preset", val);   // the engine ignores a re-pick of the current patch
                resync = true;
            }
        }
        lock_.unlock();
        if (favChanged && !resync) displayDirty_.store(true);   // new names in the PRESET menu and the status text
        if (resync)
        {
            if (!moveKeep_ && moveIdx_ >= 0) { store(moveIdx_, 0.0f); mv_.valid = false; }   // a patch loaded another way: no movement
            moveKeep_ = false;
            syncFromEngine(true);
            displayDirty_.store(true);   // the worker makes the host call, never the audio thread
        }
    }

    void pushAllToEngine()
    {
        bankTarget_.store(-1); bankSteps_.store(0); bankHost_.store(-1);   // a restored state: no turn in progress
        const auto& t = paramSpecs();
        char val[32];
        lock_.lock();
        for (size_t i = 1; i < t.size(); ++i)
        {
            dirty_[i].store(false);
            if ((int)i == moveIdx_ || (t[i].flags & (kText | kMomentary))) continue;
            snprintf(val, sizeof(val), "%d", getInt((int)i));
            v2_set_param(inst_, t[i].key, val);
        }
        dirty_[0].store(false);
        lock_.unlock();
    }

    // Set a parameter's value without calling parameterChanged (so it is not written back to the engine).
    void store(int i, float plain)
    {
        values_[(size_t)i]->store(param(i).toNormalised(plain), std::memory_order_relaxed);
    }

    // Read every value param back from the engine without marking it dirty.
    // fresh: skip values the host moved within the last 300 ms (an envelope handle still under the finger), so a read-back
    // never pulls it away mid-drag.
    void syncFromEngine(bool fresh = false)
    {
        const long long now = nowMs();
        const auto& t = paramSpecs();
        char buf[64];
        for (size_t i = 0; i < t.size(); ++i)
        {
            const ParamSpec& s = t[i];
            if ((int)i == moveIdx_ || (s.flags & (kText | kMomentary))) continue;
            if (fresh && now - hostAt_[i].load(std::memory_order_relaxed) < 300) continue;
            buf[0] = 0;
            if (v2_get_param(inst_, s.key, buf, sizeof(buf)) <= 0 || !buf[0]) continue;
            store((int)i, (float)atoi(buf));
        }
    }

    // ---- GENERATE: a musically-ruled random voice (audio thread, engine lock held) ----------------------------------------------
    // GENERATE: a new algorithm; carriers (the operators that reach the output) stay at ratio 1, fine 0, so the key note
    // never moves; modulators get ratios, levels and envelopes from the chosen style. Lower amounts vary the CURRENT voice by that
    // much (levels, envelopes, velocity, detune, feedback; modulator ratios now and then), keeping its algorithm and ratios.
    // Never touched: transpose, octave, LFO, operator ON states, carrier ratios, oscillator mode, output level.
    struct GenStyle
    {
        int cr[4], cl[4], mr[4], ml[4];
        int ratios[10]; int nratio; bool inharm;
        int modLo, modHi, fbLo, fbHi;
    };

    int chaosFlavour_ = 0;
    int rr(int lo, int hi) { return hi <= lo ? lo : lo + (int)(rng_() % (unsigned)(hi - lo + 1)); }
    static int clampi(int v, int lo, int hi) { return v < lo ? lo : v > hi ? hi : v; }
    void gset(const char* fmt, int op, const char* what, int v)
    {
        char key[32], val[16];
        snprintf(key, sizeof(key), fmt, op, what);
        snprintf(val, sizeof(val), "%d", v);
        v2_set_param(inst_, key, val);
    }
    int gget(const char* fmt, int op, const char* what)
    {
        char key[32], val[32] = "";
        snprintf(key, sizeof(key), fmt, op, what);
        return v2_get_param(inst_, key, val, sizeof(val)) > 0 ? atoi(val) : 0;
    }
    int gets(const char* key)
    {
        char val[32] = "";
        return v2_get_param(inst_, key, val, sizeof(val)) > 0 ? atoi(val) : 0;
    }

    // Some key scaling adds character (bass warmer, highs brighter or softer). A style gets it on about half the operators, gently;
    // CHAOS on most of them, deeper, with any curve and break point.
    void keyScaling(int o, bool chaos)
    {
        const bool on = rr(0, 99) < (chaos ? 75 : 45);
        gset("op%d_%s", o, "key_bp", on ? (chaos ? rr(0, 99) : rr(28, 60)) : 39);
        gset("op%d_%s", o, "key_ld", on ? rr(0, chaos ? 70 : 28) : 0);
        gset("op%d_%s", o, "key_rd", on ? rr(0, chaos ? 70 : 28) : 0);
        gset("op%d_%s", o, "key_lc", on ? rr(0, 3) : 0);
        gset("op%d_%s", o, "key_rc", on ? rr(0, 3) : 0);
    }

    // MOVE slider: movement is SEEDED when a voice is generated or mutated (an LFO, and a wandering shape for each modulator), then the
    // slider fades it in and out of that voice (0 = the voice as generated, 100 = full movement). A patch loaded any other way drops the
    // seed and resets the slider; moving the slider then seeds a fresh movement for that patch.
    struct MoveSeed
    {
        bool valid = false;
        int wave = 0, speed = 20, delay = 0, pms = 4, pmd = 50, amd = 0;
        int b_wave = 0, b_speed = 35, b_delay = 0, b_pms = 0, b_pmd = 0, b_amd = 0;
        int base[6][5] = {}, delta[6][5] = {}, amod[6] = {}, b_amod[6] = {};
    } mv_;
    int moveIdx_ = -1;
    bool moveKeep_ = false;

    void seedMove()
    {
        MoveSeed& m = mv_;
        m.valid = true;
        m.b_wave = gets("lfo_wave"); m.b_speed = gets("lfo_speed"); m.b_delay = gets("lfo_delay");
        m.b_pms = gets("lfo_pms"); m.b_pmd = gets("lfo_pmd"); m.b_amd = gets("lfo_amd");
        m.wave = rr(0, 5); m.speed = rr(0, 99) < 60 ? rr(5, 50) : rr(50, 99); m.delay = rr(0, 2) ? 0 : rr(10, 50);
        m.pms = rr(3, 7); m.pmd = rr(30, 99); m.amd = rr(0, 99) < 50 ? rr(20, 99) : 0;
        const unsigned carriers = kAlgoCarriers[clampi(gets("algorithm"), 1, 32) - 1];
        static const char* eg[5] = {"eg_r1", "eg_r2", "eg_r3", "eg_l2", "eg_l3"};
        for (int o = 1; o <= 6; ++o)
        {
            const bool car = (carriers >> (o - 1)) & 1;
            m.b_amod[o - 1] = gget("op%d_%s", o, "amp_mod");
            m.amod[o - 1] = rr(0, 2) ? rr(0, 3) : 0;
            for (int k = 0; k < 5; ++k)
            {
                m.base[o - 1][k] = gget("op%d_%s", o, eg[k]);
                m.delta[o - 1][k] = car ? 0 : (k < 3 ? -rr(10, 45) : rr(-45, 45));   // carriers stay as they are
            }
        }
    }

    void applyMove()
    {
        if (moveIdx_ < 0) return;
        const int a100 = clampi(getInt(moveIdx_), 0, 100);
        if (!mv_.valid) seedMove();
        const MoveSeed& m = mv_;
        const float a = a100 / 100.0f;
        auto lf = [&](const char* k, int v) { char b[16]; snprintf(b, sizeof(b), "%d", v); v2_set_param(inst_, k, b); };
        auto mix = [&](int from, int to) { return from + (int)std::lround((to - from) * a); };
        lf("lfo_wave", a100 > 0 ? m.wave : m.b_wave); lf("lfo_speed", a100 > 0 ? m.speed : m.b_speed); lf("lfo_delay", a100 > 0 ? m.delay : m.b_delay);
        lf("lfo_pms", a100 > 0 ? std::max(m.b_pms, m.pms) : m.b_pms);
        lf("lfo_pmd", mix(m.b_pmd, std::max(m.b_pmd, m.pmd))); lf("lfo_amd", mix(m.b_amd, std::max(m.b_amd, m.amd)));
        static const char* eg[5] = {"eg_r1", "eg_r2", "eg_r3", "eg_l2", "eg_l3"};
        for (int o = 1; o <= 6; ++o)
        {
            gset("op%d_%s", o, "amp_mod", mix(m.b_amod[o - 1], std::max(m.b_amod[o - 1], m.amod[o - 1])));
            for (int k = 0; k < 5; ++k)
                gset("op%d_%s", o, eg[k], clampi(m.base[o - 1][k] + (int)std::lround(m.delta[o - 1][k] * a), k < 3 ? 6 : 0, 99));
        }
        apply_patch_params((dx7_instance_t*)inst_);
    }
    int gets_op(int o, const char* what) { return gget("op%d_%s", o, what); }

    void generateVoice(bool mutate)
    {
        static const GenStyle styles[6] = {
            /* PLUCK */ {{99, 70, 50, 60}, {99, 70, 0, 0}, {99, 75, 55, 60}, {99, 55, 10, 0}, {1, 2, 3, 4, 5, 7}, 6, false, 45, 85, 0, 4},
            /* BELL  */ {{99, 45, 35, 40}, {99, 75, 40, 0}, {99, 50, 40, 50}, {99, 60, 25, 0}, {1, 2, 3, 4, 5, 6, 7, 9, 11, 14}, 10, true, 50, 90, 0, 3},
            /* PAD   */ {{40, 40, 40, 30}, {99, 99, 95, 0}, {35, 35, 40, 30}, {99, 90, 80, 0}, {1, 1, 2, 2, 3, 4}, 6, false, 35, 70, 0, 3},
            /* BASS  */ {{99, 80, 75, 75}, {99, 95, 85, 0}, {99, 85, 70, 70}, {99, 60, 40, 0}, {0, 1, 1, 2, 3}, 5, false, 55, 85, 2, 6},
            /* EP    */ {{99, 50, 35, 55}, {99, 85, 35, 0}, {99, 70, 50, 55}, {99, 50, 0, 0}, {1, 1, 14}, 3, false, 40, 75, 0, 3},
            /* LEAD  */ {{95, 80, 80, 65}, {99, 99, 92, 0}, {95, 80, 80, 70}, {99, 90, 80, 0}, {1, 2, 3, 4, 5}, 5, false, 55, 90, 2, 6},
        };
        // LEAD sometimes plays as an ORGAN: everything sustained, harmonic ratios, little modulation
        static const GenStyle organ = {{99, 99, 99, 90}, {99, 99, 99, 0}, {99, 99, 99, 90}, {99, 99, 99, 0}, {1, 2, 3, 4, 6, 8}, 6, false, 20, 55, 0, 2};
        const int sv = styleValue();   // 0..5 a style, 6 = ALL (a random style each press), 7 = CHAOS (no rules)
        const bool chaos = sv >= 7;
        if (chaos && !mutate)
        {   // LFO movement: vibrato / growl / tremolo, chosen per press
            chaosFlavour_ = rr(0, 4);
            auto lf = [&](const char* k, int v) { char b[16]; snprintf(b, sizeof(b), "%d", v); v2_set_param(inst_, k, b); };
            lf("lfo_wave", rr(0, 5)); lf("lfo_speed", rr(0, 99) < 50 ? rr(5, 45) : rr(45, 99)); lf("lfo_delay", rr(0, 3) ? 0 : rr(10, 60));
            lf("lfo_pms", rr(0, 7)); lf("lfo_pmd", rr(0, 99) < 70 ? rr(10, 99) : 0); lf("lfo_amd", rr(0, 99) < 50 ? rr(10, 99) : 0);
        }
        const int si = sv == 6 ? rr(0, 5) : clampi(sv, 0, 5);
        const GenStyle& st = (si == 5 && rr(0, 99) < 25) ? organ : styles[si];
        const int amount = clampi(amountValue(), 0, 100);
        const bool full = !mutate;
        const float f = amount / 100.0f;
        int algo = full ? rr(1, 32) : clampi(gets("algorithm"), 1, 32);
        if (full) { char v[16]; snprintf(v, sizeof(v), "%d", algo); v2_set_param(inst_, "algorithm", v); }
        if (chaos && !mutate) { algo = rr(1, 32); char v[16]; snprintf(v, sizeof(v), "%d", algo); v2_set_param(inst_, "algorithm", v); }
        const unsigned carriers = kAlgoCarriers[algo - 1];
        int ncar = 0;
        for (int o = 0; o < 6; ++o) ncar += (carriers >> o) & 1;
        const int egk = 8;   // EG parameter order: r1..r4, l1..l4
        static const char* egName[egk] = {"eg_r1", "eg_r2", "eg_r3", "eg_r4", "eg_l1", "eg_l2", "eg_l3", "eg_l4"};
        for (int o = 1; o <= 6; ++o)
        {
            const bool car = (carriers >> (o - 1)) & 1;
            if (full && chaos)
            {   // CHAOS: anything goes. Only a guard so a patch is not silent: the first carrier is always audible.
                const bool first = o == (int)(__builtin_ctz(carriers) + 1);
                // flavour per press: 0 GROWL (low ratios, beating detune, hot feedback), 1 BUZZ (ratios 1-2, slow-moving modulators),
                // 2 METAL (inharmonic, decaying), 3 SWEEP (slow evolving modulators), 4 ANYTHING (old behaviour, mostly low)
                static const int lowPool[10] = {0, 0, 1, 1, 1, 2, 2, 3, 4, 5};
                const int fl = chaosFlavour_;
                gset("op%d_%s", o, "osc_mode", rr(0, 99) < 3 ? 1 : 0);
                int ratio = fl == 1 ? rr(1, 2) : fl == 2 ? rr(2, 17) : fl == 4 ? (rr(0, 99) < 25 ? rr(0, 31) : lowPool[rr(0, 9)]) : lowPool[rr(0, 9)];
                gset("op%d_%s", o, "coarse", car && rr(0, 99) < 60 ? lowPool[rr(0, 6)] : ratio);
                gset("op%d_%s", o, "fine", fl == 2 ? rr(0, 99) : (rr(0, 2) == 0 ? rr(0, 99) : 0));
                gset("op%d_%s", o, "detune", fl == 0 || fl == 1 ? rr(-7, 7) : rr(-4, 4));
                gset("op%d_%s", o, "level", first ? rr(85, 99) : car ? rr(40, 99) : (fl == 3 ? rr(30, 85) : rr(20, 90)));
                // a carrier always releases to silence (L4 = 0) in a few seconds at most (R4 >= 40), or a patch would ring on forever
                const bool slow = !car && (fl == 1 || fl == 3);
                for (int k = 0; k < 4; ++k) gset("op%d_%s", o, egName[k], first && k == 0 ? rr(60, 99) : (car && k == 3 ? rr(40, 99) : slow ? rr(8, 55) : rr(5, 99)));
                for (int k = 0; k < 4; ++k) gset("op%d_%s", o, egName[4 + k], first && k == 0 ? 99 : (car && k == 3 ? 0 : (slow && k == 0 ? rr(40, 99) : rr(0, 99))));
                gset("op%d_%s", o, "vel_sens", rr(0, 7));
                gset("op%d_%s", o, "amp_mod", rr(0, 2) ? rr(0, 3) : 0);
                gset("op%d_%s", o, "rate_scale", rr(0, 7));
                keyScaling(o, true);
            }
            else if (full)
            {
                if (car)
                {
                    { int r = rr(0, 99); gset("op%d_%s", o, "coarse", r < 94 ? 1 : r < 98 ? 2 : 0); }   // mostly the key note, sometimes an octave/fifth-ish colour
                    gset("op%d_%s", o, "fine", rr(0, 9) == 0 ? rr(0, 8) : 0); gset("op%d_%s", o, "osc_mode", 0);
                    int lv = o == 1 || ncar == 1 ? 99 : rr(78, 99) - 4 * std::max(0, ncar - 3);
                    gset("op%d_%s", o, "level", clampi(lv, 60, 99));
                    gset("op%d_%s", o, "detune", rr(0, 2) ? 0 : rr(-5, 5));
                }
                else
                {
                    static const int wide[12] = {0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 15};
                    int ratio = rr(0, 99) < 15 ? wide[rr(0, 11)] : st.ratios[rr(0, st.nratio - 1)];
                    gset("op%d_%s", o, "coarse", ratio); gset("op%d_%s", o, "osc_mode", 0);
                    gset("op%d_%s", o, "fine", (st.inharm ? rr(0, 1) : rr(0, 9) == 0) ? rr(0, 60) : 0);
                    int ml = rr(st.modLo - 15, st.modHi + 10);
                    if (rr(0, 5) == 0) ml = rr(10, 99);   // now and then a modulator off the style's range
                    gset("op%d_%s", o, "level", clampi(ml, 0, 99));
                    gset("op%d_%s", o, "detune", rr(-3, 3));
                }
                const int* R = car ? st.cr : st.mr; const int* L = car ? st.cl : st.ml;
                const bool wild = rr(0, 99) < (car ? 6 : 22);   // a modulator with its own random shape instead of the style's
                for (int k = 0; k < 4; ++k) gset("op%d_%s", o, egName[k], wild ? rr(car && k == 3 ? 40 : 15, 99) : clampi(R[k] + rr(-22, 14), car && k == 3 ? 40 : 8, 99));   // carrier release: never slower than R4 40
                gset("op%d_%s", o, "eg_l1", car ? 99 : clampi(wild ? rr(40, 99) : L[0] + rr(-25, 0), 30, 99));
                for (int k = 1; k < 3; ++k) gset("op%d_%s", o, egName[4 + k], wild ? rr(car && k == 2 ? 35 : 0, 99) : clampi(L[k] + rr(-20, 16), 0, 99));   // a carrier keeps an audible sustain
                gset("op%d_%s", o, "eg_l4", 0);
                gset("op%d_%s", o, "vel_sens", rr(0, 7));
                gset("op%d_%s", o, "amp_mod", 0);
                gset("op%d_%s", o, "rate_scale", rr(0, 4));
                keyScaling(o, false);
            }
            else
            {   // vary the current voice by `amount`
                auto jit = [&](const char* what, int lo, int hi, float range) {
                    int v = gget("op%d_%s", o, what);
                    int d = (int)std::lround((rr(-100, 100) / 100.0f) * f * range);
                    gset("op%d_%s", o, what, clampi(v + d, lo, hi));
                };
                jit("level", car ? 70 : 0, 99, 30);
                for (int k = 0; k < 4; ++k) jit(egName[k], car && k == 3 ? 40 : 5, 99, 35);   // carrier release stays at R4 40 or faster
                for (int k = 1; k < 3; ++k) jit(egName[4 + k], 0, 99, 35);
                if (!car) jit("eg_l1", 40, 99, 25);
                jit("vel_sens", 0, 7, 3);
                jit("key_ld", 0, 99, 25);
                jit("key_rd", 0, 99, 25);
                jit("detune", -7, 7, 3);
                if (!car && rr(0, 99) < (int)(f * 50))
                {
                    gset("op%d_%s", o, "coarse", chaos ? rr(0, 31) : st.ratios[rr(0, st.nratio - 1)]);
                    gset("op%d_%s", o, "osc_mode", 0);
                }
            }
        }
        // the voice itself: feedback; the pitch EG is flattened so notes do not glide (the key note stays put)
        if (full)
        {
            char v[16]; snprintf(v, sizeof(v), "%d", chaos ? (chaosFlavour_ <= 1 ? rr(5, 7) : rr(2, 7)) : rr(st.fbLo, std::min(7, st.fbHi + 2))); v2_set_param(inst_, "feedback", v);
            if (!chaos) for (int k = 1; k <= 4; ++k)
            {
                char key[24]; snprintf(key, sizeof(key), "pitch_eg_r%d", k); v2_set_param(inst_, key, "99");
                snprintf(key, sizeof(key), "pitch_eg_l%d", k); v2_set_param(inst_, key, "50");
            }
        }
        else
        {
            int fb = clampi(gets("feedback") + (int)std::lround((rr(-100, 100) / 100.0f) * f * 4), 0, 7);
            char v[16]; snprintf(v, sizeof(v), "%d", fb); v2_set_param(inst_, "feedback", v);
        }
        // a name for the LCD and for +FAV
        dx7_instance_t* d = (dx7_instance_t*)inst_;
        apply_patch_params(d);
        char nm[11];
        snprintf(nm, sizeof(nm), "GEN %-5d", rr(0, 9999));
        memset(d->current_patch + 145, ' ', 10);
        memcpy(d->current_patch + 145, nm, strlen(nm) < 10 ? strlen(nm) : 10);
        snprintf(d->patch_name, sizeof(d->patch_name), "%s", nm);
    }

    int styleValue() { return getInt(styleIdx()); }
    int amountValue() { return getInt(amountIdx()); }
    int styleIdx() { static int i = findParam("gen_style"); return i; }
    int amountIdx() { static int i = findParam("gen_amount"); return i; }
    static int findParam(const char* key)
    {
        const auto& t = paramSpecs();
        for (size_t i = 0; i < t.size(); ++i) if (!strcmp(t[i].key, key)) return (int)i;
        return 0;
    }

    void* inst_ = nullptr;
    std::string cartDir_;
    std::atomic<bool>* dirty_ = nullptr;
    std::atomic<long long>* hostAt_ = nullptr;   // when the host last moved each parameter (ms)
    int presetCountdown_ = -1, presetTarget_ = 0;
    std::string pendingState_;
    EngineLock lock_;
    int16_t pcm_[N * 2] = {};
    int pcmPos_ = N;   // next unread frame of pcm_ (N = empty)
};

MPC_PLUGIN_ENTRY(DexedPlugin)
