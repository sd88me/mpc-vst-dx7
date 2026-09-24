/* Regression test for the "bank_name/patch_name readouts never refresh" bug (docs/NOTES.md,
 * "RESOLVED: bank_name/patch_name readouts never refreshed"). Verifies BOTH halves of the fix --
 *   (1) the DSP's own get_param("bank_name"/"patch_name") actually returns updated text after
 *       a bank/preset change (this was already correct, confirmed repeatedly in this file's
 *       history -- re-checked here as a belt-and-suspenders regression guard), and
 *   (2) the WRAPPER calls audioMasterUpdateDisplay (opcode 42) after a param changes another
 *       param's displayed text indirectly (the step_target branch: next_syx_bank, prev_syx_bank,
 *       preset_next, preset_prev) and after a direct setParameter -- this was the actual missing
 *       piece; MPC has no other signal to re-poll a degenerate min==max readout's text.
 *
 * Build (needs a schwung-dx7 checkout, e.g. .scratch/schwung-dx7, and this port's generated
 * build/params.h with MODULE_DIR pointed at a flat folder of .syx files -- see build.sh/
 * docs/NOTES.md for the MODULE_DIR convention this port actually uses, no nested "banks/"):
 *   gcc -c ../../wrapper/vst2_wrap.c -I<params.h dir> -o vst2_wrap.o
 *   g++ -c <schwung-dx7>/src/dsp/dx7_plugin.cpp <schwung-dx7>/src/dsp/msfa/*.cc \
 *       <schwung-dx7>/src/dsp/msfa/porta.cpp -I<schwung-dx7>/src/dsp
 *   gcc -c host_test_readout.c -o host_test_readout.o
 *   g++ vst2_wrap.o *.o host_test_readout.o -lm -o host_test_readout && ./host_test_readout */
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
typedef struct AEffect AEffect;
typedef intptr_t (*cb)(AEffect*,int32_t,int32_t,intptr_t,void*,float);
struct AEffect { int32_t magic; intptr_t (*d)(AEffect*,int32_t,int32_t,intptr_t,void*,float);
 void*p; void (*setP)(AEffect*,int32_t,float); float (*getP)(AEffect*,int32_t);
 int32_t np,npar,ni,no,flags; intptr_t r1,r2; int32_t a,b,c; float io; void*obj,*user; int32_t uid,ver;
 void (*pr)(AEffect*,float**,float**,int32_t); void*pdr; char f[56]; };
typedef struct { int32_t type,byteSize,deltaFrames,flags,noteLength,noteOffset; unsigned char m[4]; char x[4]; } ME;
typedef struct { int32_t n; intptr_t r; void* ev[2]; } EV;
extern AEffect* VSTPluginMain(cb);

static int g_update_display_calls = 0;
static intptr_t host(AEffect*e,int32_t op,int32_t i,intptr_t v,void*p,float o){
    (void)e;(void)i;(void)v;(void)p;(void)o;
    static double ti[16];
    if (op == 7) { ti[4] = 128.0; ((int32_t*)&ti[8])[5] = 1 << 10; return (intptr_t)ti; }
    if (op == 42) { g_update_display_calls++; return 1; }  /* audioMasterUpdateDisplay */
    return 0;
}

static int find_param(AEffect *a, const char *want) {
    char s[256];
    for (int j = 0; j < a->npar; j++) {
        s[0] = 0;
        a->d(a, 8, j, 0, s, 0);
        if (strcmp(s, want) == 0) return j;
    }
    return -1;
}

/* One processReplacing call, tiny block -- enough to drain any deferred host callback. */
static void pump(AEffect *a) {
    float L[16], R[16], *out[2] = {L, R};
    a->pr(a, 0, out, 16);
}

int main(){
    AEffect *a = VSTPluginMain(host);
    int p_preset = find_param(a, "Preset");
    int p_patchname = find_param(a, "Patch Name");
    int p_bankname = find_param(a, "Bank Name");
    int p_next_patch = find_param(a, "Next Patch");
    int p_next_bank = find_param(a, "Next Bank");
    printf("param idx: preset=%d patch_name=%d bank_name=%d next_patch=%d next_bank=%d\n",
           p_preset, p_patchname, p_bankname, p_next_patch, p_next_bank);

    char before[64], after[64];
    a->d(a,7,p_patchname,0,before,0);
    printf("patch_name before preset_next: '%s'\n", before);

    g_update_display_calls = 0;
    a->setP(a, p_next_patch, 1.0f);   /* fires the step_target branch */
    pump(a);                          /* drains the deferred audioMasterUpdateDisplay */
    a->d(a,7,p_patchname,0,after,0);
    printf("patch_name after preset_next:  '%s'\n", after);
    printf("audioMasterUpdateDisplay calls after preset_next: %d\n", g_update_display_calls);

    int patch_string_changed = strcmp(before, after) != 0;
    int display_updated_1 = g_update_display_calls > 0;
    printf("%s: DSP's patch_name string actually changed\n", patch_string_changed ? "PASS" : "FAIL");
    printf("%s: wrapper called audioMasterUpdateDisplay after the change\n", display_updated_1 ? "PASS" : "FAIL");

    char bank_before[64], bank_after[64];
    a->d(a,7,p_bankname,0,bank_before,0);
    g_update_display_calls = 0;
    a->setP(a, p_next_bank, 1.0f);
    pump(a);
    a->d(a,7,p_bankname,0,bank_after,0);
    printf("bank_name before/after next_syx_bank: '%s' -> '%s'\n", bank_before, bank_after);
    printf("audioMasterUpdateDisplay calls after next_syx_bank: %d\n", g_update_display_calls);
    int bank_string_changed = strcmp(bank_before, bank_after) != 0;
    int display_updated_2 = g_update_display_calls > 0;
    printf("%s: DSP's bank_name string actually changed\n", bank_string_changed ? "PASS" : "FAIL");
    printf("%s: wrapper called audioMasterUpdateDisplay after the change\n", display_updated_2 ? "PASS" : "FAIL");

    /* A direct, unrelated param set (e.g. a Q-Link turn on Algorithm) should ALSO trigger a
     * deferred audioMasterUpdateDisplay per the fix (any setParameter marks need_update_display,
     * not just step_target triggers) -- matches jv880's fix exactly (both a stepper arrow tap AND
     * a direct Q-Link turn needed to refresh a readout). */
    int p_algo = find_param(a, "Algorithm");
    g_update_display_calls = 0;
    a->setP(a, p_algo, 0.3f);
    pump(a);
    printf("audioMasterUpdateDisplay calls after a plain Algorithm set: %d\n", g_update_display_calls);
    printf("%s: plain param set also triggers a deferred UpdateDisplay\n",
           g_update_display_calls > 0 ? "PASS" : "FAIL");

    /* No spurious calls when nothing changed this block. */
    g_update_display_calls = 0;
    pump(a);
    printf("audioMasterUpdateDisplay calls on an idle block: %d\n", g_update_display_calls);
    printf("%s: no spurious UpdateDisplay calls when nothing changed\n",
           g_update_display_calls == 0 ? "PASS" : "FAIL");

    int overall_pass = patch_string_changed && display_updated_1 && bank_string_changed && display_updated_2;
    printf("\n%s\n", overall_pass ? "OVERALL: PASS" : "OVERALL: FAIL");

    a->d(a,1,0,0,0,0);
    return overall_pass ? 0 : 1;
}
