<script setup lang="ts">
import { ref, reactive, nextTick } from 'vue';
import { open } from '@tauri-apps/plugin-dialog';
import { Command } from '@tauri-apps/plugin-shell';
import { resolveResource } from '@tauri-apps/api/path';
import { 
  FolderOpen, Loader2,
  Terminal, ScanFace, 
  CheckCircle2, AlertCircle, Info,
  MonitorPlay, GitBranch
} from 'lucide-vue-next';

// State
const config = reactive({
  templatesFolder: '',
  inputFolder: '',
  outputHighFolder: '',
  outputFixedFolder: '',
  enableHigh: true,
  enableFixed: true,
  targetWidth: 456,
  targetHeight: 564
});

const isProcessing = ref(false);
const logs = ref<Array<{id: number, time: string, msg: string, type: 'info'|'success'|'error'}>>([]);
const logContainerRef = ref<HTMLElement | null>(null);

// Git State
const isGitInput = ref(false);
const enableGitInput = ref(false);
const isGitHigh = ref(false);
const enableGitHigh = ref(false);
const isGitFixed = ref(false);
const enableGitFixed = ref(false);

// Logging
let logIdCounter = 0;
const addLog = (msg: string, type: 'info' | 'success' | 'error' = 'info') => {
  const time = new Date().toLocaleTimeString('zh-CN', { hour12: false });
  logs.value.push({ id: logIdCounter++, time, msg, type });
  nextTick(() => {
    if (logContainerRef.value) {
      logContainerRef.value.scrollTop = logContainerRef.value.scrollHeight;
    }
  });
};

// Git Helpers
const checkGitRepo = async (path: string): Promise<boolean> => {
  try {
    const cmd = Command.create('git', ['-C', path, 'rev-parse', '--is-inside-work-tree']);
    const out = await cmd.execute();
    return out.code === 0 && out.stdout.trim() === 'true';
  } catch (e) {
    return false;
  }
};

const executeGitOps = async (path: string, msg: string) => {
  addLog(`正在执行 Git 操作: ${path}`, 'info');
  try {
    const addCmd = Command.create('git', ['-C', path, 'add', '.']);
    await addCmd.execute();
    
    const commitCmd = Command.create('git', ['-C', path, 'commit', '-m', msg]);
    const commitOut = await commitCmd.execute();
    if (commitOut.code !== 0) {
        if (commitOut.stdout.includes('nothing to commit') || commitOut.stderr.includes('nothing to commit')) {
            addLog('Git: 没有需要提交的更改', 'info');
            return;
        }
        addLog(`Git Commit 失败: ${commitOut.stderr}`, 'error');
    } else {
        addLog('Git Commit 成功', 'success');
    }

    const pushCmd = Command.create('git', ['-C', path, 'push']);
    const pushOut = await pushCmd.execute();
    if (pushOut.code === 0) {
        addLog('Git Push 成功', 'success');
    } else {
        addLog(`Git Push 失败: ${pushOut.stderr}`, 'error');
    }

  } catch (e: any) {
    addLog(`Git 操作异常: ${e.message}`, 'error');
  }
};

const selectFolder = async (key: 'templatesFolder' | 'inputFolder' | 'outputHighFolder' | 'outputFixedFolder') => {
  try {
    const selected = await open({
      directory: true,
      multiple: false,
    });
    if (selected) {
      config[key] = selected as string;
      
      // Git checks
      if (key === 'inputFolder') isGitInput.value = await checkGitRepo(config.inputFolder);
      if (key === 'outputHighFolder') isGitHigh.value = await checkGitRepo(config.outputHighFolder);
      if (key === 'outputFixedFolder') isGitFixed.value = await checkGitRepo(config.outputFixedFolder);
    }
  } catch (err) {
    addLog(`选择文件夹失败: ${err}`, 'error');
  }
};

const startProcess = async () => {
    if (!config.templatesFolder || !config.inputFolder) {
        addLog("请配置模板和输入目录", 'error');
        return;
    }
    if (!config.enableHigh && !config.enableFixed) {
        addLog("请至少启用一种输出模式", 'error');
        return;
    }
    if (config.enableHigh && !config.outputHighFolder) {
         config.outputHighFolder = config.inputFolder + "_high_res";
         isGitHigh.value = await checkGitRepo(config.outputHighFolder);
         addLog(`默认设置高清输出目录: ${config.outputHighFolder}`, 'info');
    }
    if (config.enableFixed && !config.outputFixedFolder) {
         config.outputFixedFolder = config.inputFolder + "_fixed";
         isGitFixed.value = await checkGitRepo(config.outputFixedFolder);
         addLog(`默认设置固定输出目录: ${config.outputFixedFolder}`, 'info');
    }

    isProcessing.value = true;
    logs.value = [];
    addLog("正在启动智能裁剪任务 (Python Engine)...", 'info');

    try {
        const scriptPath = await resolveResource('python/smart_crop.py');
        addLog(`Loading script: ${scriptPath}`, 'info');
        
        const args = [
            scriptPath,
            '--templates', config.templatesFolder,
            '--input', config.inputFolder,
            '--width', config.targetWidth.toString(),
            '--height', config.targetHeight.toString()
        ];

        if (config.enableHigh) {
            args.push('--output-high', config.outputHighFolder);
        }
        if (config.enableFixed) {
            args.push('--output-fixed', config.outputFixedFolder);
        }

        const cmd = Command.create('python', args);
        
        cmd.on('close', async (data) => {
            isProcessing.value = false;
            addLog(`任务结束 (Exit Code: ${data.code})`, data.code === 0 ? 'success' : 'error');
            
            if (data.code === 0) {
                // Git Ops
                if (enableGitInput.value && isGitInput.value) {
                    await executeGitOps(config.inputFolder, "Auto-commit input: Smart Crop");
                }
                if (enableGitHigh.value && isGitHigh.value && config.enableHigh) {
                    await executeGitOps(config.outputHighFolder, "Auto-commit High Res: Smart Crop");
                }
                if (enableGitFixed.value && isGitFixed.value && config.enableFixed) {
                    await executeGitOps(config.outputFixedFolder, "Auto-commit Fixed: Smart Crop");
                }
            }
        });

        cmd.on('error', (error) => {
            addLog(`执行错误: ${error}`, 'error');
            isProcessing.value = false;
        });

        cmd.stdout.on('data', (line) => {
            try {
                const data = JSON.parse(line);
                if (data.msg) {
                    addLog(data.msg, data.type || 'info');
                }
            } catch (e) {
                // Fallback for non-JSON lines
                if (line.trim()) addLog(line, 'info');
            }
        });
        
        cmd.stderr.on('data', (line) => {
             if (line.trim()) addLog(line, 'error');
        });

        const child = await cmd.spawn();
        addLog(`Process started (PID: ${child.pid})`, 'info');

    } catch (e: any) {
        addLog(`启动失败: ${e.message}`, 'error');
        isProcessing.value = false;
    }
};
</script>

<template>
  <div class="flex flex-col gap-4 max-w-6xl mx-auto h-full">
    
    <!-- Hero / Title -->
    <div class="flex items-end justify-between shrink-0">
      <div class="space-y-1">
        <h2 class="text-xl font-bold text-white tracking-tight">智能模版裁剪</h2>
        <p class="text-zinc-400 text-xs">基于 SIFT 特征匹配，自动定位并裁剪目标区域</p>
        <p class="text-zinc-400 text-xs">该模块基于 EIHRTeam/tools/image-cropping-tool 修改</p>
      </div>
      
      <div v-if="isProcessing" class="flex items-center gap-2 bg-zinc-900/50 px-3 py-1.5 rounded-lg border border-white/5 backdrop-blur">
          <Loader2 class="w-3.5 h-3.5 animate-spin text-primary" />
          <span class="text-[10px] font-mono text-zinc-300">Processing...</span>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-12 gap-4 h-full min-h-0">
      
      <!-- Left: Configuration -->
      <div class="lg:col-span-7 flex flex-col gap-4 h-full min-h-0 relative">
        <div class="flex-1 overflow-y-auto pr-2 custom-scrollbar space-y-4">
            
            <!-- Folders -->
            <section class="bg-zinc-900/40 border border-white/5 rounded-xl p-4 space-y-4">
                <div class="space-y-3">
                     <!-- Templates Input -->
                     <div class="space-y-1">
                        <label class="text-[9px] uppercase text-zinc-500 font-bold tracking-wider ml-1">Templates Folder (模版库)</label>
                        <div class="flex gap-2">
                             <div class="relative flex-1">
                                <input 
                                  type="text" 
                                  v-model="config.templatesFolder"
                                  placeholder="选择包含模版图片的文件夹..." 
                                  class="w-full bg-black/20 border border-white/5 rounded-lg px-3 py-2 text-xs text-zinc-200 placeholder-zinc-600 font-mono focus:border-primary focus:ring-1 focus:ring-primary/50 outline-none transition-all"
                                />
                                <div class="absolute right-2 top-1/2 -translate-y-1/2 text-zinc-600">
                                    <CheckCircle2 v-if="config.templatesFolder" class="w-3.5 h-3.5 text-emerald-500/80" />
                                </div>
                             </div>
                             <button @click="selectFolder('templatesFolder')" class="px-3 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-zinc-300 transition-colors">
                                 <FolderOpen class="w-4 h-4" />
                             </button>
                        </div>
                     </div>

                     <!-- Source Input -->
                     <div class="space-y-1">
                        <label class="text-[9px] uppercase text-zinc-500 font-bold tracking-wider ml-1">Source Input (原始图片)</label>
                        <div class="flex gap-2">
                             <div class="relative flex-1">
                                <input 
                                  type="text" 
                                  v-model="config.inputFolder"
                                  placeholder="选择需要裁剪的原始图片文件夹..." 
                                  class="w-full bg-black/20 border border-white/5 rounded-lg px-3 py-2 text-xs text-zinc-200 placeholder-zinc-600 font-mono focus:border-primary focus:ring-1 focus:ring-primary/50 outline-none transition-all"
                                />
                                <div class="absolute right-2 top-1/2 -translate-y-1/2 text-zinc-600">
                                    <CheckCircle2 v-if="config.inputFolder" class="w-3.5 h-3.5 text-emerald-500/80" />
                                </div>
                             </div>
                             <button @click="selectFolder('inputFolder')" class="px-3 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-zinc-300 transition-colors">
                                 <FolderOpen class="w-4 h-4" />
                             </button>
                        </div>
                        
                        <!-- Git Toggle -->
                        <div v-if="isGitInput" class="px-1 pt-1 flex items-center gap-2 animate-fade-in">
                             <GitBranch class="w-3.5 h-3.5 text-orange-500" />
                             <span class="text-[10px] text-zinc-500 font-mono">Git Repo Detected</span>
                             <div class="flex-1"></div>
                             <label class="flex items-center gap-2 cursor-pointer select-none">
                                 <input type="checkbox" v-model="enableGitInput" class="rounded bg-zinc-800 border-zinc-700 text-primary focus:ring-primary/50 w-3.5 h-3.5" />
                                 <span class="text-[10px] text-zinc-400">Auto Commit & Push</span>
                             </label>
                        </div>
                     </div>
                </div>
            </section>

            <!-- Outputs -->
            <section class="bg-zinc-900/40 border border-white/5 rounded-xl p-4 space-y-4">
                <div class="flex items-center gap-2 mb-2">
                    <MonitorPlay class="w-4 h-4 text-zinc-400" />
                    <h3 class="text-xs font-semibold text-zinc-200">输出配置</h3>
                </div>

                <!-- High Res Output -->
                <div class="bg-black/20 rounded-lg p-3 border border-white/5 space-y-3">
                    <div class="flex items-center justify-between">
                         <label class="flex items-center gap-2 cursor-pointer select-none">
                             <input type="checkbox" v-model="config.enableHigh" class="rounded bg-zinc-800 border-zinc-700 text-primary focus:ring-primary/50 w-3.5 h-3.5" />
                             <span class="text-xs font-medium text-zinc-300">高清裁剪 (High Res)</span>
                         </label>
                    </div>
                    
                    <div v-if="config.enableHigh" class="flex gap-2 animate-fade-in">
                         <input 
                            type="text" 
                            v-model="config.outputHighFolder"
                            placeholder="默认: [输入目录]_high_res" 
                            class="flex-1 bg-zinc-900/50 border border-zinc-800 rounded px-2 py-1.5 text-[11px] text-zinc-300 font-mono focus:border-zinc-600 outline-none"
                         />
                         <button @click="selectFolder('outputHighFolder')" class="px-2.5 bg-zinc-800 hover:bg-zinc-700 rounded text-zinc-400">
                             <FolderOpen class="w-3.5 h-3.5" />
                         </button>
                    </div>
                </div>

                <!-- Fixed Output -->
                <div class="bg-black/20 rounded-lg p-3 border border-white/5 space-y-3">
                    <div class="flex items-center justify-between">
                         <label class="flex items-center gap-2 cursor-pointer select-none">
                             <input type="checkbox" v-model="config.enableFixed" class="rounded bg-zinc-800 border-zinc-700 text-primary focus:ring-primary/50 w-3.5 h-3.5" />
                             <span class="text-xs font-medium text-zinc-300">固定尺寸 (Fixed Size)</span>
                         </label>
                    </div>
                    
                    <div v-if="config.enableFixed" class="space-y-3 animate-fade-in">
                        <div class="flex gap-2 items-center">
                            <div class="flex items-center gap-2 bg-zinc-900/50 px-2 py-1 rounded border border-zinc-800">
                                <span class="text-[10px] text-zinc-500 uppercase">W</span>
                                <input type="number" v-model="config.targetWidth" class="w-12 bg-transparent text-right text-xs font-mono outline-none" />
                            </div>
                            <span class="text-zinc-600 text-xs">x</span>
                            <div class="flex items-center gap-2 bg-zinc-900/50 px-2 py-1 rounded border border-zinc-800">
                                <span class="text-[10px] text-zinc-500 uppercase">H</span>
                                <input type="number" v-model="config.targetHeight" class="w-12 bg-transparent text-right text-xs font-mono outline-none" />
                            </div>
                        </div>

                        <div class="flex gap-2">
                             <input 
                                type="text" 
                                v-model="config.outputFixedFolder"
                                placeholder="默认: [输入目录]_fixed" 
                                class="flex-1 bg-zinc-900/50 border border-zinc-800 rounded px-2 py-1.5 text-[11px] text-zinc-300 font-mono focus:border-zinc-600 outline-none"
                             />
                             <button @click="selectFolder('outputFixedFolder')" class="px-2.5 bg-zinc-800 hover:bg-zinc-700 rounded text-zinc-400">
                                 <FolderOpen class="w-3.5 h-3.5" />
                             </button>
                        </div>
                    </div>
                </div>
            </section>
        </div>

        <!-- Run Button -->
        <button 
          @click="startProcess" 
          :disabled="isProcessing"
          class="w-full mt-auto group relative overflow-hidden py-4 rounded-xl font-bold text-white shadow-[0_0_20px_rgba(16,185,129,0.3)] transition-all active:scale-[0.98] disabled:opacity-70 disabled:cursor-not-allowed disabled:shadow-none hover:shadow-[0_0_30px_rgba(16,185,129,0.5)] border border-emerald-500/20"
          :class="isProcessing ? 'bg-zinc-800' : 'bg-gradient-to-r from-emerald-500 to-teal-600'"
        >
          <div class="relative z-10 flex items-center justify-center gap-3">
             <ScanFace v-if="!isProcessing" class="w-5 h-5" />
             <Loader2 v-else class="w-5 h-5 animate-spin" />
             <span class="text-base tracking-wide">{{ isProcessing ? 'Processing...' : '开始' }}</span>
          </div>
          <!-- Shine Effect -->
          <div v-if="!isProcessing" class="absolute inset-0 -translate-x-full group-hover:translate-x-full transition-transform duration-1000 bg-gradient-to-r from-transparent via-white/20 to-transparent skew-x-12"></div>
        </button>
      </div>

      <!-- Right: Console -->
      <div class="lg:col-span-5 flex flex-col h-full min-h-0">
        <div class="flex-1 bg-[#0c0c0e] rounded-xl border border-zinc-800 flex flex-col shadow-inner overflow-hidden relative">
          <!-- Window Controls Decoration -->
          <div class="h-8 bg-zinc-900/80 border-b border-zinc-800 flex items-center px-3 justify-between shrink-0">
              <div class="flex gap-1.5">
                  <div class="w-2.5 h-2.5 rounded-full bg-red-500/20 border border-red-500/50"></div>
                  <div class="w-2.5 h-2.5 rounded-full bg-yellow-500/20 border border-yellow-500/50"></div>
                  <div class="w-2.5 h-2.5 rounded-full bg-emerald-500/20 border border-emerald-500/50"></div>
              </div>
              <div class="flex items-center gap-2 text-[9px] text-zinc-500 font-mono">
                  <Terminal class="w-3 h-3" />
                  <span>PYTHON OUTPUT</span>
              </div>
          </div>

          <div ref="logContainerRef" class="flex-1 p-3 overflow-y-auto font-mono text-[10px] space-y-2 scrollbar-hide">
              <template v-if="logs.length > 0">
                <div v-for="log in logs" :key="log.id" class="flex gap-2 animate-slide-up leading-relaxed">
                  <span class="text-zinc-600 shrink-0 select-none">{{ log.time }}</span>
                  <div class="flex items-start gap-1.5">
                     <CheckCircle2 v-if="log.type === 'success'" class="w-3 h-3 text-emerald-500 mt-0.5 shrink-0" />
                     <AlertCircle v-else-if="log.type === 'error'" class="w-3 h-3 text-rose-500 mt-0.5 shrink-0" />
                     <Info v-else class="w-3 h-3 text-blue-500 mt-0.5 shrink-0" />
                     
                     <span :class="{
                       'text-zinc-300': log.type === 'info',
                       'text-emerald-400': log.type === 'success',
                       'text-rose-400': log.type === 'error'
                     }" class="break-all whitespace-pre-wrap">{{ log.msg }}</span>
                  </div>
                </div>
              </template>
              
              <!-- Empty State -->
              <div v-else class="h-full flex flex-col items-center justify-center text-zinc-700 space-y-3 opacity-40">
                <div class="w-10 h-10 rounded-lg bg-zinc-800 flex items-center justify-center">
                    <Cpu class="w-5 h-5" />
                </div>
                <p class="text-[10px]">Waiting for task...</p>
              </div>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #3f3f46;
  border-radius: 4px;
}
</style>
