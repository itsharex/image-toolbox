<script setup lang="ts">
import { ref, reactive, computed, nextTick, watch } from 'vue';
import { open } from '@tauri-apps/plugin-dialog';
import { Command } from '@tauri-apps/plugin-shell';
import { readDir, mkdir, exists, stat, readTextFile } from '@tauri-apps/plugin-fs';
import { homeDir, join } from '@tauri-apps/api/path';
import { 
  FolderOpen, Play, Loader2,
  Move, Crop, Terminal, Settings2,
  CheckCircle2, AlertCircle, Info, ChevronRight, Upload, FileJson, ChevronDown, GitBranch, Layers, ArrowLeft
} from 'lucide-vue-next';

// --- Types ---
type ResizeMethod = 'fixed' | 'ratio';
type DefaultMode = 'crop' | 'pad';
type Format = 'png' | 'jpg' | 'webp';

interface Profile {
  enable?: boolean;
  description?: string;
  input_folder?: string;
  output_folder?: string;
  format?: string;
  resize_method?: string;
  width?: number;
  height?: number;
  scale_factor?: number;
  fixed_mode?: string;
  [key: string]: any;
}

interface BatchTask {
    name: string;
    config: any;
    description?: string;
    isGitInput: boolean;
    isGitOutput: boolean;
    enableGitInput: boolean;
    enableGitOutput: boolean;
}

// --- State ---
const config = reactive({
  inputFolder: '',
  outputFolder: '',
  resizeMethod: 'fixed' as ResizeMethod,
  width: 1920,
  height: 1080,
  scaleFactor: 0.5,
  format: 'png' as Format,
  fixedMode: 'crop' as DefaultMode,
});

const profiles = ref<Record<string, Profile>>({});
const activeProfile = ref<string>('');
const configFilePath = ref<string>('');

const isProcessing = ref(false);
const logs = ref<Array<{id: number, time: string, msg: string, type: 'info'|'success'|'error'}>>([]);
const progress = ref({ current: 0, total: 0 });
const logContainerRef = ref<HTMLElement | null>(null);
const isDragging = ref<'input' | 'output' | null>(null);

// Git State
const isGitInput = ref(false);
const isGitOutput = ref(false);
const enableGitInput = ref(false);
const enableGitOutput = ref(false);

// Batch Review State
const reviewMode = ref(false);
const batchQueue = ref<BatchTask[]>([]);
const activeReviewIndex = ref(0);

// --- Computed ---
const progressPercentage = computed(() => {
  if (progress.value.total === 0) return 0;
  return Math.round((progress.value.current / progress.value.total) * 100);
});

// --- Helpers ---
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

const getDirname = (path: string) => {
    const sep = path.includes('\\') ? '\\' : '/';
    return path.substring(0, path.lastIndexOf(sep));
};

const resolvePath = async (base: string, relative: string) => {
    if (relative.match(/^[a-zA-Z]:\\/i) || relative.startsWith('/')) return relative;
    return await join(base, relative);
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

const applyProfile = async (profileName: string) => {
  const profile = profiles.value[profileName];
  if (!profile) return;

  if (configFilePath.value) {
      const baseDir = getDirname(configFilePath.value);
      if (profile.input_folder) {
          config.inputFolder = await resolvePath(baseDir, profile.input_folder);
          isGitInput.value = await checkGitRepo(config.inputFolder);
      }
      if (profile.output_folder) {
          config.outputFolder = await resolvePath(baseDir, profile.output_folder);
          isGitOutput.value = await checkGitRepo(config.outputFolder);
      }
  }

  if (profile.format && ['png', 'jpg', 'webp'].includes(profile.format)) {
    config.format = profile.format as Format;
  }
  
  if (profile.resize_method) {
    if (profile.resize_method === 'fixed') {
      config.resizeMethod = 'fixed';
      if (profile.width) config.width = profile.width;
      if (profile.height) config.height = profile.height;
      if (profile.fixed_mode) config.fixedMode = profile.fixed_mode as DefaultMode;
    } else if (profile.resize_method === 'ratio') {
      config.resizeMethod = 'ratio';
      if (profile.scale_factor) config.scaleFactor = profile.scale_factor;
    }
  }
  
  addLog(`已应用配置: ${profileName}`, 'info');
};

const loadConfigFile = async (path: string) => {
  try {
    if (await exists(path)) {
       const content = await readTextFile(path);
       const data = JSON.parse(content);
       
       if (typeof data === 'object') {
          profiles.value = data;
          configFilePath.value = path;
          
          const keys = Object.keys(data);
          if (keys.length > 0) {
             activeProfile.value = keys[0];
             addLog(`已加载配置文件: ${path}`, 'success');
          }
       }
    }
  } catch (e) {
    console.error("Failed to load config", e);
  }
};

const selectConfigFile = async () => {
    try {
        const selected = await open({
            multiple: false,
            filters: [{ name: 'JSON Config', extensions: ['json'] }]
        });
        if (selected) {
            await loadConfigFile(selected as string);
        }
    } catch (e) {
        addLog(`选择文件失败: ${e}`, 'error');
    }
};

const selectFolder = async (target: 'input' | 'output') => {
  try {
    const selected = await open({
      directory: true,
      multiple: false,
      defaultPath: await homeDir(),
    });
    if (selected) {
      const path = selected as string;
      if (target === 'input') {
          config.inputFolder = path;
          isGitInput.value = await checkGitRepo(path);
          
          if (!config.outputFolder) {
              config.outputFolder = path + "_processed";
              isGitOutput.value = await checkGitRepo(config.outputFolder);
          }
          
          const potentialConfig = await join(path, 'settings.json');
          await loadConfigFile(potentialConfig);
      }
      else {
          config.outputFolder = path;
          isGitOutput.value = await checkGitRepo(path);
      }
    }
  } catch (err) {
    console.error(err);
  }
};

const handleDrop = async (event: DragEvent, target: 'input' | 'output') => {
  isDragging.value = null;
  const files = event.dataTransfer?.files;
  
  if (files && files.length > 0) {
    const file = files[0] as any; 
    const path = file.path || file.name;
    
    if (path) {
       try {
         const info = await stat(path);
         if (info.isDirectory) {
            if (target === 'input') {
               config.inputFolder = path;
               isGitInput.value = await checkGitRepo(path);

               if (!config.outputFolder) {
                   config.outputFolder = path + "_processed";
                   isGitOutput.value = await checkGitRepo(config.outputFolder);
               }
               addLog(`已载入输入目录: ${path}`, 'success');
               
               const potentialConfig = await join(path, 'settings.json');
               await loadConfigFile(potentialConfig);
               
            } else {
               config.outputFolder = path;
               isGitOutput.value = await checkGitRepo(path);
               addLog(`已设置输出目录: ${path}`, 'success');
            }
         } else {
            addLog('拖入的不是文件夹', 'error');
         }
       } catch (e) {
         addLog(`无法读取路径: ${path}`, 'error');
       }
    }
  }
};

// Core processing logic
const processTask = async (taskConfig: any, taskName: string, gitOptions?: { enableInput: boolean, enableOutput: boolean }) => {
    addLog(`[${taskName}] 开始任务...`, 'info');
    
    if (!taskConfig.inputFolder || !taskConfig.outputFolder) {
        addLog(`[${taskName}] 路径未配置，跳过`, 'error');
        return;
    }

    if (!(await exists(taskConfig.outputFolder))) {
       await mkdir(taskConfig.outputFolder, { recursive: true });
    }

    const entries = await readDir(taskConfig.inputFolder);
    const validExtensions = ['.png', '.jpg', '.jpeg', '.bmp', '.webp'];
    const filesToProcess = entries.filter(e => !e.isDirectory && validExtensions.some(ext => e.name.toLowerCase().endsWith(ext)));

    if (filesToProcess.length === 0) {
        addLog(`[${taskName}] 无图片文件`, 'error');
        return;
    }

    addLog(`[${taskName}] 发现 ${filesToProcess.length} 个文件`, 'info');
    progress.value.total += filesToProcess.length;

    let filterString = '';
    if (taskConfig.resizeMethod === 'ratio') {
        filterString = `scale=iw*${taskConfig.scaleFactor}:-1:flags=lanczos`;
    } else {
        if (taskConfig.fixedMode === 'crop') {
            filterString = `scale=${taskConfig.width}:${taskConfig.height}:force_original_aspect_ratio=increase:flags=lanczos,crop=${taskConfig.width}:${taskConfig.height}`;
        } else {
            filterString = `scale=${taskConfig.width}:${taskConfig.height}:force_original_aspect_ratio=decrease:flags=lanczos,pad=${taskConfig.width}:${taskConfig.height}:(ow-iw)/2:(oh-ih)/2:color=0x00000000`;
        }
    }

    // Concurrency Limit
    const CONCURRENCY_LIMIT = 4;
    const activePromises: Promise<void>[] = [];

    const processFile = async (file: any) => {
      try {
          const inputPath = await join(taskConfig.inputFolder, file.name);
          const nameWithoutExt = file.name.substring(0, file.name.lastIndexOf('.'));
          const outputFilename = `${nameWithoutExt}.${taskConfig.format}`;
          const outputPath = await join(taskConfig.outputFolder, outputFilename);

          const qualityArgs: string[] = [];
          if (['jpg', 'jpeg'].includes(taskConfig.format)) {
              qualityArgs.push('-q:v', '1'); 
          } else if (taskConfig.format === 'webp') {
              qualityArgs.push('-q:v', '100');
          }

          const args = ['-y', '-v', 'error', '-i', inputPath, '-vf', filterString, ...qualityArgs, outputPath];
          
          const command = Command.create('ffmpeg', args);
          const output = await command.execute();

          if (output.code === 0) {
            addLog(`[${taskName}] 处理成功: ${file.name}`, 'success');
          } else {
            addLog(`[${taskName}] 失败: ${file.name} - ${output.stderr}`, 'error');
          }
      } catch (e: any) {
          addLog(`[${taskName}] 异常: ${file.name} - ${e.message}`, 'error');
      } finally {
          progress.value.current++;
      }
    };

    for (const file of filesToProcess) {
       const p = processFile(file);
       activePromises.push(p);
       if (activePromises.length >= CONCURRENCY_LIMIT) {
           await Promise.race(activePromises);
           // Remove finished promises
           // Note: Promise.race returns the value of the first resolved promise, 
           // but we need to remove the specific promise object from the array.
           // A simpler way is to wrap the promise to remove itself.
           // However, for simplicity in this context without external libs:
           // We simply await one slot to free up.
           // Let's implement a better pool mechanism below.
       }
    }
    
    // Better implementation of pool inside the loop
    const results = [];
    const executing = new Set<Promise<void>>();

    for (const file of filesToProcess) {
        const p = processFile(file).then(() => { executing.delete(p); });
        results.push(p);
        executing.add(p);
        
        if (executing.size >= CONCURRENCY_LIMIT) {
            await Promise.race(executing);
        }
    }
    await Promise.all(results);

    // Git Auto-Push for this specific task
    const runGitInput = gitOptions ? gitOptions.enableInput : enableGitInput.value;
    const runGitOutput = gitOptions ? gitOptions.enableOutput : enableGitOutput.value;

    if (runGitInput && (await checkGitRepo(taskConfig.inputFolder))) {
        await executeGitOps(taskConfig.inputFolder, `Auto-commit input: ${taskName}`);
    }
    if (runGitOutput && (await checkGitRepo(taskConfig.outputFolder))) {
        await executeGitOps(taskConfig.outputFolder, `Auto-commit output: ${taskName}`);
    }
};

const startProcess = async () => {
  isProcessing.value = true;
  logs.value = [];
  progress.value = { current: 0, total: 0 };

  try {
      await processTask(config, 'Manual');
      addLog('手动任务执行完毕', 'success');
  } catch (error: any) {
    addLog(`系统错误: ${error.message}`, 'error');
  } finally {
    isProcessing.value = false;
  }
};

const runAllProfiles = async () => {
    if (!profiles.value || Object.keys(profiles.value).length === 0) return;
    
    try {
        const baseDir = getDirname(configFilePath.value);
        batchQueue.value = [];
        
        for (const [name, profile] of Object.entries(profiles.value)) {
            if (profile.enable !== false) {
                const taskConfig = { ...config }; 
                
                if (profile.format) taskConfig.format = profile.format as Format;
                if (profile.resize_method) {
                    if (profile.resize_method === 'fixed') {
                        taskConfig.resizeMethod = 'fixed';
                        if (profile.width) taskConfig.width = profile.width;
                        if (profile.height) taskConfig.height = profile.height;
                        if (profile.fixed_mode) taskConfig.fixedMode = profile.fixed_mode as DefaultMode;
                    } else if (profile.resize_method === 'ratio') {
                        taskConfig.resizeMethod = 'ratio';
                        if (profile.scale_factor) taskConfig.scaleFactor = profile.scale_factor;
                    }
                }
                
                if (profile.input_folder) taskConfig.inputFolder = await resolvePath(baseDir, profile.input_folder);
                if (profile.output_folder) taskConfig.outputFolder = await resolvePath(baseDir, profile.output_folder);
                
                // Check Git Status for this specific task
                const taskIsGitInput = await checkGitRepo(taskConfig.inputFolder);
                const taskIsGitOutput = await checkGitRepo(taskConfig.outputFolder);

                batchQueue.value.push({
                    name: name,
                    config: taskConfig,
                    description: profile.description,
                    isGitInput: taskIsGitInput,
                    isGitOutput: taskIsGitOutput,
                    enableGitInput: false,
                    enableGitOutput: false
                });
            }
        }
        
        if (batchQueue.value.length > 0) {
            reviewMode.value = true;
            activeReviewIndex.value = 0;
        } else {
            addLog('没有可执行的配置 (No enabled profiles)', 'error');
        }
        
    } catch (e: any) {
        addLog(`预处理失败: ${e.message}`, 'error');
    }
};

const executeBatch = async () => {
    isProcessing.value = true;
    logs.value = [];
    progress.value = { current: 0, total: 0 };
    
    try {
        for (const task of batchQueue.value) {
            await processTask(task.config, task.name, {
                enableInput: task.enableGitInput,
                enableOutput: task.enableGitOutput
            });
        }
        addLog('所有批量任务执行完毕', 'success');
        reviewMode.value = false;
    } catch (e: any) {
        addLog(`批量执行异常: ${e.message}`, 'error');
    } finally {
        isProcessing.value = false;
    }
};

const cancelReview = () => {
    reviewMode.value = false;
    batchQueue.value = [];
};

watch(activeProfile, (newVal: string) => {
    if (newVal) applyProfile(newVal);
});

</script>

<template>
  <div class="flex flex-col gap-4 max-w-6xl mx-auto h-full">
    
    <!-- Hero / Title -->
    <div class="flex items-end justify-between shrink-0">
      <div class="space-y-1">
        <h2 class="text-xl font-bold text-white tracking-tight">图片批量压缩</h2>
        <p class="text-zinc-400 text-xs">配置目标分辨率或缩放比例，执行批量压缩任务</p>
      </div>
      
      <div v-if="isProcessing" class="flex items-center gap-3 bg-zinc-900/50 px-3 py-1.5 rounded-lg border border-white/5 backdrop-blur">
         <span class="text-[10px] font-mono text-primary">{{ progress.current }} / {{ progress.total }}</span>
         <div class="w-24 h-1 bg-zinc-800 rounded-full overflow-hidden">
             <div class="h-full bg-primary transition-all duration-300 ease-out" :style="{ width: `${progressPercentage}%` }"></div>
         </div>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-12 gap-4 h-full min-h-0">
      
      <!-- Left: Configuration OR Review Mode -->
      <div class="lg:col-span-7 flex flex-col gap-4 h-full min-h-0 relative">
        
        <!-- Standard Mode -->
        <div v-if="!reviewMode" class="flex flex-col gap-4 h-full">
            <div class="flex-1 overflow-y-auto pr-2 custom-scrollbar space-y-4">
                <!-- Config Profile Card -->
                <section class="bg-zinc-900/40 border border-white/5 rounded-xl p-3 flex items-center gap-3">
                     <button 
                        @click="selectConfigFile"
                        class="flex items-center gap-2 px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg text-xs transition-colors border border-white/5"
                     >
                        <FileJson class="w-3.5 h-3.5" />
                        <span>加载配置</span>
                     </button>
                     
                     <div v-if="Object.keys(profiles).length > 0" class="flex-1 flex items-center gap-2 bg-black/20 hover:bg-black/30 border border-white/5 hover:border-white/10 rounded-lg px-3 relative group transition-colors">
                         <span class="text-[10px] text-zinc-500 font-bold uppercase tracking-wider shrink-0">Profile</span>
                         <select 
                            v-model="activeProfile" 
                            class="flex-1 bg-transparent py-1.5 text-xs text-zinc-200 appearance-none focus:outline-none cursor-pointer w-full"
                         >
                            <option v-for="(_, k) in profiles" :key="k" :value="k" class="bg-zinc-900 text-zinc-200">{{ k }}</option>
                         </select>
                         <ChevronDown class="w-3 h-3 text-zinc-500 group-hover:text-zinc-300 transition-colors pointer-events-none absolute right-3" />
                     </div>
                     
                     <!-- Run All Button -->
                     <button 
                        v-if="Object.keys(profiles).length > 0"
                        @click="runAllProfiles"
                        class="shrink-0 w-8 h-8 rounded-lg bg-zinc-800/50 hover:bg-primary/20 hover:text-primary text-zinc-400 border border-white/5 flex items-center justify-center transition-colors"
                        title="批量执行所有配置"
                     >
                        <Layers class="w-4 h-4" />
                     </button>
    
                     <div v-else class="flex-1 text-[10px] text-zinc-600 italic px-2">
                         未加载配置文件 (默认使用 settings.json)
                     </div>
                </section>
    
                <!-- File Paths Card -->
                <section class="group relative bg-zinc-900/40 border border-white/5 hover:border-white/10 rounded-xl p-1 transition-all">
                  <div class="absolute inset-0 bg-gradient-to-b from-white/5 to-transparent opacity-0 group-hover:opacity-100 rounded-xl transition-opacity pointer-events-none"></div>
                  
                  <div class="relative p-3 space-y-3">
                     <!-- Input -->
                     <div 
                       class="relative overflow-hidden bg-black/20 border rounded-lg p-1 transition-all group/input flex gap-3 items-center"
                       :class="isDragging === 'input' ? 'border-primary bg-primary/10' : 'border-white/5 hover:border-primary/30 hover:bg-black/30'"
                       @dragover.prevent="isDragging = 'input'"
                       @dragleave.prevent="isDragging = null"
                       @drop.prevent="handleDrop($event, 'input')"
                     >
                        <button 
                          @click="selectFolder('input')"
                          class="shrink-0 w-10 h-10 rounded-md bg-zinc-800/80 hover:bg-zinc-700 hover:text-white flex flex-col items-center justify-center text-zinc-400 transition-all cursor-pointer border border-transparent hover:border-zinc-600"
                          title="浏览文件夹"
                        >
                            <Upload class="w-3.5 h-3.5 mb-0.5" />
                            <span class="text-[8px] font-bold uppercase">Load</span>
                        </button>
    
                        <div class="flex-1 min-w-0 flex flex-col justify-center py-0.5">
                            <label class="text-[9px] uppercase text-zinc-500 font-bold tracking-wider mb-0.5 ml-1">输入目录 (Input)</label>
                            <input 
                              type="text" 
                              v-model="config.inputFolder"
                              placeholder="粘贴路径或拖拽文件夹..." 
                              class="w-full bg-transparent border-none p-0.5 text-xs text-zinc-200 placeholder-zinc-600 font-mono focus:ring-0 focus:outline-none truncate"
                            />
                        </div>
                        
                        <div class="pr-2 text-zinc-600">
                            <CheckCircle2 v-if="config.inputFolder" class="w-3.5 h-3.5 text-emerald-500/80" />
                            <ChevronRight v-else class="w-3.5 h-3.5 opacity-50" />
                        </div>
                     </div>
                     
                     <!-- Git Input Toggle -->
                     <div v-if="isGitInput" class="px-2 flex items-center gap-2 animate-fade-in">
                         <GitBranch class="w-3.5 h-3.5 text-orange-500" />
                         <span class="text-[10px] text-zinc-500 font-mono">Git Repo Detected</span>
                         <div class="flex-1"></div>
                         <label class="flex items-center gap-2 cursor-pointer select-none">
                             <input type="checkbox" v-model="enableGitInput" class="rounded bg-zinc-800 border-zinc-700 text-primary focus:ring-primary/50 w-3.5 h-3.5" />
                             <span class="text-[10px] text-zinc-400">Auto Commit & Push</span>
                         </label>
                     </div>
    
                     <!-- Output -->
                     <div 
                       class="relative overflow-hidden bg-black/20 border rounded-lg p-1 transition-all group/output flex gap-3 items-center"
                       :class="isDragging === 'output' ? 'border-primary bg-primary/10' : 'border-white/5 hover:border-primary/30 hover:bg-black/30'"
                       @dragover.prevent="isDragging = 'output'"
                       @dragleave.prevent="isDragging = null"
                       @drop.prevent="handleDrop($event, 'output')"
                     >
                        <button 
                          @click="selectFolder('output')"
                          class="shrink-0 w-10 h-10 rounded-md bg-zinc-800/80 hover:bg-zinc-700 hover:text-white flex flex-col items-center justify-center text-zinc-400 transition-all cursor-pointer border border-transparent hover:border-zinc-600"
                          title="选择保存位置"
                        >
                            <FolderOpen class="w-3.5 h-3.5 mb-0.5" />
                            <span class="text-[8px] font-bold uppercase">Save</span>
                        </button>
    
                        <div class="flex-1 min-w-0 flex flex-col justify-center py-0.5">
                            <label class="text-[9px] uppercase text-zinc-500 font-bold tracking-wider mb-0.5 ml-1">输出目录 (Output)</label>
                            <input 
                              type="text" 
                              v-model="config.outputFolder"
                              placeholder="粘贴路径或拖拽文件夹..." 
                              class="w-full bg-transparent border-none p-0.5 text-xs text-zinc-200 placeholder-zinc-600 font-mono focus:ring-0 focus:outline-none truncate"
                            />
                        </div>
    
                        <div class="pr-2 text-zinc-600">
                            <CheckCircle2 v-if="config.outputFolder" class="w-3.5 h-3.5 text-emerald-500/80" />
                            <ChevronRight v-else class="w-3.5 h-3.5 opacity-50" />
                        </div>
                     </div>
                     
                     <!-- Git Output Toggle -->
                     <div v-if="isGitOutput" class="px-2 flex items-center gap-2 animate-fade-in">
                         <GitBranch class="w-3.5 h-3.5 text-orange-500" />
                         <span class="text-[10px] text-zinc-500 font-mono">Git Repo Detected</span>
                         <div class="flex-1"></div>
                         <label class="flex items-center gap-2 cursor-pointer select-none">
                             <input type="checkbox" v-model="enableGitOutput" class="rounded bg-zinc-800 border-zinc-700 text-primary focus:ring-primary/50 w-3.5 h-3.5" />
                             <span class="text-[10px] text-zinc-400">Auto Commit & Push</span>
                         </label>
                     </div>
                  </div>
                </section>
    
                <!-- Settings Card -->
                <section class="bg-zinc-900/40 border border-white/5 rounded-xl p-4 space-y-4">
                   <div class="flex items-center justify-between">
                       <div class="flex items-center gap-2">
                            <div class="p-1 rounded-md bg-zinc-800 text-zinc-300">
                                <Settings2 class="w-3.5 h-3.5" />
                            </div>
                            <h3 class="text-xs font-semibold text-zinc-200">处理参数</h3>
                       </div>
                       
                       <!-- Format Tabs -->
                       <div class="flex bg-black/40 rounded-lg p-0.5 border border-white/5">
                           <button 
                            v-for="fmt in ['png', 'jpg', 'webp']" :key="fmt"
                            @click="config.format = fmt as Format"
                            :class="['px-2.5 py-0.5 text-[10px] font-bold rounded-md transition-all uppercase', config.format === fmt ? 'bg-zinc-700 text-white shadow-sm' : 'text-zinc-500 hover:text-zinc-300']"
                           >
                             {{ fmt }}
                           </button>
                       </div>
                   </div>
    
                   <div class="space-y-4">
                      <!-- Method Switch -->
                      <div class="flex bg-zinc-800/30 p-0.5 rounded-lg border border-white/5">
                          <button 
                            @click="config.resizeMethod = 'fixed'"
                            class="flex-1 py-1.5 rounded-md text-[11px] font-medium transition-all flex items-center justify-center gap-1.5"
                            :class="config.resizeMethod === 'fixed' ? 'bg-zinc-700 text-white shadow' : 'text-zinc-400 hover:text-zinc-200'"
                          >
                            <Move class="w-3 h-3" /> 固定尺寸
                          </button>
                          <button 
                            @click="config.resizeMethod = 'ratio'"
                            class="flex-1 py-1.5 rounded-md text-[11px] font-medium transition-all flex items-center justify-center gap-1.5"
                            :class="config.resizeMethod === 'ratio' ? 'bg-zinc-700 text-white shadow' : 'text-zinc-400 hover:text-zinc-200'"
                          >
                            <Crop class="w-3 h-3" /> 按比例缩放
                          </button>
                      </div>
    
                      <!-- Dynamic Inputs -->
                      <div class="bg-black/20 rounded-xl p-4 border border-white/5 min-h-[120px] flex flex-col justify-center">
                          
                          <!-- Fixed Mode -->
                          <div v-if="config.resizeMethod === 'fixed'" class="space-y-4 animate-fade-in">
                              <div class="grid grid-cols-2 gap-3">
                                  <div class="space-y-1">
                                      <label class="text-[9px] text-zinc-500 uppercase font-bold tracking-wider">宽度 (px)</label>
                                      <input type="number" v-model="config.width" class="w-full bg-zinc-900 border border-zinc-700 rounded-md px-2 py-1.5 text-xs text-white focus:border-primary focus:ring-1 focus:ring-primary/50 transition-all font-mono" />
                                  </div>
                                  <div class="space-y-1">
                                      <label class="text-[9px] text-zinc-500 uppercase font-bold tracking-wider">高度 (px)</label>
                                      <input type="number" v-model="config.height" class="w-full bg-zinc-900 border border-zinc-700 rounded-md px-2 py-1.5 text-xs text-white focus:border-primary focus:ring-1 focus:ring-primary/50 transition-all font-mono" />
                                  </div>
                              </div>
                              
                              <div class="space-y-1.5">
                                <label class="text-[9px] text-zinc-500 uppercase font-bold tracking-wider">填充模式</label>
                                <div class="grid grid-cols-2 gap-2">
                                   <label class="cursor-pointer flex items-center gap-2 p-2 rounded-md border transition-all" :class="config.fixedMode === 'crop' ? 'bg-primary/10 border-primary/50' : 'bg-zinc-900/50 border-zinc-700 hover:border-zinc-600'">
                                      <input type="radio" value="crop" v-model="config.fixedMode" class="hidden" />
                                      <div class="w-3.5 h-3.5 rounded-full border flex items-center justify-center" :class="config.fixedMode === 'crop' ? 'border-primary' : 'border-zinc-500'">
                                          <div v-if="config.fixedMode === 'crop'" class="w-1.5 h-1.5 rounded-full bg-primary"></div>
                                      </div>
                                      <span class="text-[11px]" :class="config.fixedMode === 'crop' ? 'text-white' : 'text-zinc-400'">裁剪切边</span>
                                   </label>
                                   <label class="cursor-pointer flex items-center gap-2 p-2 rounded-md border transition-all" :class="config.fixedMode === 'pad' ? 'bg-primary/10 border-primary/50' : 'bg-zinc-900/50 border-zinc-700 hover:border-zinc-600'">
                                      <input type="radio" value="pad" v-model="config.fixedMode" class="hidden" />
                                      <div class="w-3.5 h-3.5 rounded-full border flex items-center justify-center" :class="config.fixedMode === 'pad' ? 'border-primary' : 'border-zinc-500'">
                                          <div v-if="config.fixedMode === 'pad'" class="w-1.5 h-1.5 rounded-full bg-primary"></div>
                                      </div>
                                      <span class="text-[11px]" :class="config.fixedMode === 'pad' ? 'text-white' : 'text-zinc-400'">留白填充</span>
                                   </label>
                                </div>
                              </div>
                          </div>
    
                          <!-- Ratio Mode -->
                          <div v-else class="space-y-4 animate-fade-in px-1">
                               <div class="flex justify-between items-end">
                                  <label class="text-[10px] text-zinc-400">缩放倍率</label>
                                  <div class="flex items-center gap-2">
                                     <input 
                                       type="number" 
                                       v-model.number="config.scaleFactor" 
                                       step="0.1"
                                       min="0.1"
                                       class="w-16 bg-zinc-900 border border-zinc-700 rounded-md px-1.5 py-0.5 text-xs text-right font-mono focus:border-primary outline-none" 
                                     />
                                     <span class="text-xs font-mono text-zinc-500">x</span>
                                  </div>
                               </div>
                               <input 
                                 type="range" 
                                 min="0.1" 
                                 max="2.0" 
                                 step="0.1" 
                                 v-model.number="config.scaleFactor" 
                                 class="w-full h-1.5 bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-primary hover:accent-primary-hover"
                               />
                               <div class="flex justify-between text-[9px] text-zinc-600 font-mono">
                                  <span>0.1x</span>
                                  <span>1.0x</span>
                                  <span>2.0x</span>
                               </div>
                          </div>
                      </div>
                   </div>
                </section>
            </div>
    
            <!-- Run Button (Standard Mode) -->
            <button 
              @click="startProcess" 
              :disabled="isProcessing"
              class="w-full mt-auto group relative overflow-hidden py-4 rounded-xl font-bold text-white shadow-[0_0_20px_rgba(99,102,241,0.3)] transition-all active:scale-[0.98] disabled:opacity-70 disabled:cursor-not-allowed disabled:shadow-none hover:shadow-[0_0_30px_rgba(99,102,241,0.5)] border border-primary/20"
              :class="isProcessing ? 'bg-zinc-800' : 'bg-gradient-to-r from-primary to-indigo-600'"
            >
              <div class="relative z-10 flex items-center justify-center gap-3">
                 <Loader2 v-if="isProcessing" class="w-5 h-5 animate-spin" />
                 <Play v-else class="w-5 h-5 fill-current" />
                 <span class="text-base tracking-wide">{{ isProcessing ? 'Processing...' : '开始' }}</span>
              </div>
              <!-- Shine Effect -->
              <div v-if="!isProcessing" class="absolute inset-0 -translate-x-full group-hover:translate-x-full transition-transform duration-1000 bg-gradient-to-r from-transparent via-white/20 to-transparent skew-x-12"></div>
            </button>
        </div>

        <!-- REVIEW MODE -->
        <div v-else class="flex flex-col h-full animate-fade-in gap-4">
            
            <!-- Review Header -->
            <div class="flex items-center gap-3">
                <button @click="cancelReview" class="p-2 hover:bg-white/10 rounded-lg transition-colors">
                    <ArrowLeft class="w-4 h-4 text-zinc-300" />
                </button>
                <div>
                    <h3 class="text-sm font-bold text-white">批量任务确认</h3>
                    <p class="text-[10px] text-zinc-500">共 {{ batchQueue.length }} 个配置项</p>
                </div>
            </div>

            <!-- Tabs -->
            <div class="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
                <button 
                    v-for="(task, idx) in batchQueue" 
                    :key="idx"
                    @click="activeReviewIndex = idx"
                    class="px-3 py-1.5 rounded-lg text-xs font-mono border whitespace-nowrap transition-all"
                    :class="activeReviewIndex === idx ? 'bg-primary/20 border-primary text-primary' : 'bg-zinc-800 border-zinc-700 text-zinc-400 hover:text-zinc-200'"
                >
                    {{ task.name }}
                </button>
            </div>

            <!-- Detail Card (Reuse style but READ ONLY) -->
            <div class="flex-1 bg-zinc-900/40 border border-white/5 rounded-xl p-4 overflow-y-auto space-y-5">
                <div class="space-y-1">
                    <h4 class="text-sm font-bold text-white">{{ batchQueue[activeReviewIndex].name }}</h4>
                    <p class="text-xs text-zinc-500 leading-relaxed">{{ batchQueue[activeReviewIndex].description || '无描述' }}</p>
                </div>

                <div class="space-y-3">
                    <div class="space-y-1">
                        <label class="text-[9px] uppercase text-zinc-500 font-bold tracking-wider">Input Folder</label>
                        <div class="px-3 py-2 bg-black/20 border border-white/5 rounded-lg text-xs font-mono text-zinc-400 truncate select-all">
                            {{ batchQueue[activeReviewIndex].config.inputFolder }}
                        </div>
                        <!-- Git Toggle -->
                        <div v-if="batchQueue[activeReviewIndex].isGitInput" class="px-1 pt-1 flex items-center gap-2">
                             <GitBranch class="w-3 h-3 text-orange-500" />
                             <label class="flex items-center gap-2 cursor-pointer select-none">
                                 <input type="checkbox" v-model="batchQueue[activeReviewIndex].enableGitInput" class="rounded bg-zinc-800 border-zinc-700 text-primary focus:ring-primary/50 w-3 h-3" />
                                 <span class="text-[10px] text-zinc-400">Auto Commit & Push Input</span>
                             </label>
                        </div>
                    </div>
                    <div class="space-y-1">
                        <label class="text-[9px] uppercase text-zinc-500 font-bold tracking-wider">Output Folder</label>
                        <div class="px-3 py-2 bg-black/20 border border-white/5 rounded-lg text-xs font-mono text-zinc-400 truncate select-all">
                            {{ batchQueue[activeReviewIndex].config.outputFolder }}
                        </div>
                        <!-- Git Toggle -->
                        <div v-if="batchQueue[activeReviewIndex].isGitOutput" class="px-1 pt-1 flex items-center gap-2">
                             <GitBranch class="w-3 h-3 text-orange-500" />
                             <label class="flex items-center gap-2 cursor-pointer select-none">
                                 <input type="checkbox" v-model="batchQueue[activeReviewIndex].enableGitOutput" class="rounded bg-zinc-800 border-zinc-700 text-primary focus:ring-primary/50 w-3 h-3" />
                                 <span class="text-[10px] text-zinc-400">Auto Commit & Push Output</span>
                             </label>
                        </div>
                    </div>
                </div>

                <div class="h-px bg-white/5"></div>

                <div class="grid grid-cols-2 gap-4 text-xs">
                    <div>
                        <span class="text-zinc-500">Format:</span> 
                        <span class="ml-2 font-mono text-zinc-300 uppercase">{{ batchQueue[activeReviewIndex].config.format }}</span>
                    </div>
                    <div>
                        <span class="text-zinc-500">Method:</span> 
                        <span class="ml-2 font-mono text-zinc-300">{{ batchQueue[activeReviewIndex].config.resizeMethod }}</span>
                    </div>
                    <div v-if="batchQueue[activeReviewIndex].config.resizeMethod === 'fixed'">
                        <span class="text-zinc-500">Size:</span> 
                        <span class="ml-2 font-mono text-zinc-300">{{ batchQueue[activeReviewIndex].config.width }}x{{ batchQueue[activeReviewIndex].config.height }}</span>
                    </div>
                    <div v-else>
                        <span class="text-zinc-500">Scale:</span> 
                        <span class="ml-2 font-mono text-zinc-300">{{ batchQueue[activeReviewIndex].config.scaleFactor }}x</span>
                    </div>
                </div>
            </div>

            <!-- Action Buttons -->
            <div class="mt-auto grid grid-cols-2 gap-3">
                <button 
                    @click="cancelReview"
                    class="py-3 rounded-xl font-bold text-zinc-400 bg-zinc-800 hover:bg-zinc-700 transition-colors"
                >
                    取消
                </button>
                <button 
                    @click="executeBatch"
                    :disabled="isProcessing"
                    class="py-3 rounded-xl font-bold text-white bg-primary hover:bg-primary-hover shadow-lg shadow-primary/20 transition-all flex items-center justify-center gap-2"
                >
                    <Play v-if="!isProcessing" class="w-4 h-4 fill-current" />
                    <Loader2 v-else class="w-4 h-4 animate-spin" />
                    {{ isProcessing ? '执行中...' : `全部执行 (${batchQueue.length})` }}
                </button>
            </div>

        </div>

      </div>

      <!-- Right: Action & Console -->
      <div class="lg:col-span-5 flex flex-col h-full min-h-0">
        
        <!-- Console -->
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
                  <span>PROCESS LOG</span>
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
                     }" class="break-all">{{ log.msg }}</span>
                  </div>
                </div>
              </template>
              
              <!-- Empty State -->
              <div v-else class="h-full flex flex-col items-center justify-center text-zinc-700 space-y-3 opacity-40">
                <div class="w-10 h-10 rounded-lg bg-zinc-800 flex items-center justify-center">
                    <Terminal class="w-5 h-5" />
                </div>
                <p class="text-[10px]">Waiting for command...</p>
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