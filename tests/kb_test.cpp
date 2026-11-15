// Offline check of the +FAV naming keyboard: loads the built plugin (build/native/dexed--dx7-.so), presses +FAV, types, SAVE / CANCEL.
//   tests/kb_test.sh   (builds it and runs it in a scratch plugin folder)
#include "mpc_vst2_abi.h"
#include <dlfcn.h>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <thread>
#include <vector>

static int g_fail = 0;
#define CHECK(c, ...) do { if (c) std::printf("  ok   "); else { std::printf("  FAIL "); g_fail++; } std::printf(__VA_ARGS__); std::printf("\n"); } while (0)
static VstIntPtr host(AEffect*, VstInt32 op, VstInt32, VstIntPtr, void*, float) { return op == audioMasterVersion ? 2400 : 0; }

static AEffect* e;
static std::vector<std::string> names;
static int find(const char* k) { for (size_t i = 0; i < names.size(); i++) if (names[i] == k) return (int)i; std::printf("no param %s\n", k); std::exit(2); }
static void run(int blocks = 6)
{
    float L[128], R[128], *out[2] = {L, R};
    for (int b = 0; b < blocks; b++) { e->processReplacing(e, nullptr, out, 128); std::this_thread::sleep_for(std::chrono::milliseconds(6)); }
}
static std::string disp(int i) { char b[128] = {0}; e->dispatcher(e, effGetParamDisplay, i, 0, b, 0); return b; }
static float val(int i) { return e->getParameter(e, i); }
static std::string prog(int i) { char b[64] = {0}; e->dispatcher(e, effGetProgramNameIndexed, i, 0, b, 0); return b; }

int main(int, char** argv)
{
    void* h = dlopen(argv[1], RTLD_NOW);
    if (!h) { std::printf("dlopen: %s\n", dlerror()); return 2; }
    auto entry = (AEffect * (*)(audioMasterCallback)) dlsym(h, "VSTPluginMain");
    e = entry(host);
    e->dispatcher(e, effSetSampleRate, 0, 0, nullptr, 44100.f);
    e->dispatcher(e, effSetBlockSize, 0, 128, nullptr, 0);
    e->dispatcher(e, effMainsChanged, 0, 1, nullptr, 0);
    for (int i = 0; i < e->numParams; i++) { char b[64] = {0}; e->dispatcher(e, effGetParamName, i, 0, b, 0); names.push_back(b); }
    run();
    // names are the display names: find the keys by the table's order instead (kb_save is last)
    std::printf("== naming keyboard (%d params)\n", e->numParams);
    CHECK(e->numParams == 274, "274 params");
    const int last = e->numParams - 1;
    names.assign((size_t)e->numParams, "");
    const char* ks = "1234567890QWERTYUIOPASDFGHJKLZXCVBNM-";
    const int first = last - 41, open = first - 1, nm = open - 1, fav = -1;
    (void)fav;
    int favSave = -1;
    for (int i = 0; i < e->numParams; i++) { char b[64] = {0}; e->dispatcher(e, effGetParamName, i, 0, b, 0); if (!std::strcmp(b, "+FAV")) favSave = i; }
    CHECK(favSave > 0, "+FAV found (%d)", favSave);
    auto press = [&](int i) { std::this_thread::sleep_for(std::chrono::milliseconds(260)); e->setParameter(e, i, 1.0f); run(); e->setParameter(e, i, 0.0f); run(); };
    auto ch = [&](char c) { return first + (int)(std::strchr(ks, c) - ks); };
    const int space = first + 37, bksp = first + 38, shift = first + 39, cancel = first + 40, save = first + 41;
    CHECK(val(open) < 0.5f, "keyboard closed at start");
    press(favSave);
    CHECK(val(open) > 0.5f, "+FAV opens the keyboard");
    press(ch('5'));
    CHECK(disp(nm) == "5_", "the first character replaces the voice's name (\"%s\")", disp(nm).c_str());
    for (int i = 0; i < 12; i++) press(bksp);
    CHECK(disp(nm) == "_", "delete empties the name (\"%s\")", disp(nm).c_str());
    press(ch('L')); press(ch('E')); press(ch('A')); press(ch('D')); press(space); press(ch('2')); press(shift); press(ch('X'));
    CHECK(disp(nm) == "Lead 2X_", "typed \"Lead 2X\" (\"%s\")", disp(nm).c_str());
    {   // one tap reported twice types once
        std::this_thread::sleep_for(std::chrono::milliseconds(260));
        e->setParameter(e, ch('Q'), 1.0f); run(); e->setParameter(e, ch('Q'), 1.0f); run(); e->setParameter(e, ch('Q'), 0.0f); run();
        CHECK(disp(nm) == "Lead 2Xq_", "a doubled tap types once (\"%s\")", disp(nm).c_str());
    }
    for (int i = 0; i < 5; i++) press(ch('Z'));
    CHECK(disp(nm) == "Lead 2Xqzz_", "names stop at 10 characters (\"%s\")", disp(nm).c_str());
    press(bksp); press(bksp); press(bksp);
    press(save);
    CHECK(val(open) < 0.5f, "SAVE closes the keyboard");
    std::string p1 = prog(1);
    CHECK(p1 == "1 Lead 2X", "PRESET menu slot 1: \"%s\"", p1.c_str());
    press(favSave); press(ch('Z')); press(cancel);
    CHECK(val(open) < 0.5f && prog(2) == "--", "CANCEL closes without saving (slot 2 \"%s\")", prog(2).c_str());
    press(ch('A'));
    CHECK(disp(nm) == disp(nm) && val(open) < 0.5f, "keys do nothing while closed");
    e->dispatcher(e, effMainsChanged, 0, 0, nullptr, 0);
    e->dispatcher(e, effClose, 0, 0, nullptr, 0);
    if (g_fail) { std::printf("%d FAILED\n", g_fail); return 1; }
    std::printf("OK\n");
    return 0;
}
