<script setup lang="ts">
import { ref, reactive, nextTick, computed } from 'vue';
import { open } from '@tauri-apps/plugin-dialog';
import { Command } from '@tauri-apps/plugin-shell';
import { join } from '@tauri-apps/api/path';
import { readDir, mkdir, stat } from '@tauri-apps/plugin-fs';
import { 
  Film, Loader2, Play, 
  Terminal, Settings2, 
  CheckCircle2, AlertCircle, Info, 
  FileVideo, Trash2, Plus, 
  MonitorPlay, Minimize2, Scissors, Repeat,
  FolderOpen, Folder, Upload, ChevronRight
} from 'lucide-vue-next';

// --- Types ---
interface VideoFile {
  originalPath: string; // Absolute path to file
  relativePath: string; // Relative to the import root (for structure preservation)
  name: string;
  status: 'pending' | 'processing' | 'done' | 'error';
}

// --- State ---
const files = ref<VideoFile[]>([]);
const isProcessing = ref(false);
const logs = ref<Array<{id: number, time: string, msg: string, type: 'info'|'success'|'error'}>>([]);
const logContainerRef = ref<HTMLElement | null>(null);
const progress = ref({ current: 0, total: files.value.length });
const isDragging = ref<'files' | 'output' | null>(null);

const config = reactive({
  outputFolder: '',
  fps: 15,
  keepOriginalResolution: false,
  width: 800, // 0 = auto/original
  loop: 0, // 0 = infinite
  pixelFormat: 'rgba',
  compressionLevel: 9, // 0-9
  mpdecimate: false, // Remove duplicate frames
  pred: 5, // Prediction method (5=mixed)
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

// Recursive directory scan
const scanDirectory = async (dirPath: string, rootPath: string): Promise<VideoFile[]> => {
    const results: VideoFile[] = [];
    const validExtensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.gif'];

    try {
        const entries = await readDir(dirPath);
        for (const entry of entries) {
            const entryPath = await join(dirPath, entry.name);
            
            if (entry.isDirectory) {
                const subResults = await scanDirectory(entryPath, rootPath);
                results.push(...subResults);
            } else {
                const lowerName = entry.name.toLowerCase();
                if (validExtensions.some(ext => lowerName.endsWith(ext))) {
                    // Calculate relative path manually since path.relative might not be available or reliable cross-platform in frontend
                    // Assuming entryPath starts with rootPath. 
                    // rootPath: "C:\\Videos"
                    // entryPath: "C:\\Videos\\Sub\\A.mp4"
                    // relative: "Sub\\A.mp4"
                    
                    let relative = entryPath.replace(rootPath, '');
                    if (relative.startsWith('\\') || relative.startsWith('/')) {
                        relative = relative.substring(1);
                    }
                    
                    // If rootPath was the file's direct parent, relative is just filename.
                    // If we dragged a folder, we want the folder structure *inside* that folder to be preserved.
                    // But if we import "C:\\Videos", and we find "C:\\Videos\\A.mp4", relative is "A.mp4".
                    // The output will be "Output\\A.apng".
                    // If we find "C:\\Videos\\Sub\\B.mp4", relative is "Sub\\B.mp4". Output: "Output\\Sub\\B.apng".
                    // This seems correct for "Merge contents" behavior.
                    
                    results.push({
                        originalPath: entryPath,
                        relativePath: relative,
                        name: entry.name,
                        status: 'pending'
                    });
                }
            }
        }
    } catch (e) {
        addLog(`扫描目录失败: ${dirPath} - ${e}`, 'error');
    }
    return results;
};

const addFiles = async () => {
  try {
    const selected = await open({
      multiple: true,
      filters: [{ name: 'Video', extensions: ['mp4', 'mov', 'avi', 'mkv', 'webm', 'gif'] }]
    });
    
    if (selected) {
       const paths = Array.isArray(selected) ? selected : [selected];
       for (const path of paths) {
           const name = path.split(/[\\/]/).pop() || path;
           if (!files.value.some(f => f.originalPath === path)) {
               files.value.push({
                   originalPath: path, 
                   relativePath: name, // Flat structure for individual files
                   name, 
                   status: 'pending' 
               });
           }
       }
    }
  } catch (e) {
    addLog(`添加文件失败: ${e}`, 'error');
  }
};

const addFolder = async () => {
    try {
        const selected = await open({
            directory: true,
            multiple: true
        });
        
        if (selected) {
            const paths = Array.isArray(selected) ? selected : [selected];
            addLog(`正在扫描 ${paths.length} 个文件夹...`, 'info');
            
            for (const path of paths) {
                const newFiles = await scanDirectory(path, path);
                
                let addedCount = 0;
                for (const file of newFiles) {
                    if (!files.value.some(f => f.originalPath === file.originalPath)) {
                        files.value.push(file);
                        addedCount++;
                    }
                }
                addLog(`已添加 ${addedCount} 个视频来自: ${path}`, 'success');
            }
        }
    } catch (e) {
        addLog(`添加文件夹失败: ${e}`, 'error');
    }
};

const selectOutputFolder = async () => {
    try {
        const selected = await open({
            directory: true,
            multiple: false
        });
        if (selected) {
            config.outputFolder = selected as string;
        }
    } catch (e) {
        addLog(`选择输出目录失败: ${e}`, 'error');
    }
};

const handleDrop = async (event: DragEvent, target: 'files' | 'output') => {
  isDragging.value = null;
  const droppedFiles = event.dataTransfer?.files;
  
  if (droppedFiles && droppedFiles.length > 0) {
      if (target === 'output') {
          // Expecting a single folder for output
          const file = droppedFiles[0] as any;
          // Basic check if it's a folder (not perfect without fs.stat, but we try)
          // We can use the stat API to confirm
           try {
               const path = file.path || file.name;
               const info = await stat(path);
               if (info.isDirectory) {
                   config.outputFolder = path;
                   addLog(`已设置输出目录: ${path}`, 'success');
               } else {
                   addLog('输出目标必须是文件夹', 'error');
               }
           } catch(e) {
               addLog('无法验证路径', 'error');
           }
      } else {
          // Input files/folders
          addLog(`处理拖入的 ${droppedFiles.length} 个项目...`, 'info');
          for (let i = 0; i < droppedFiles.length; i++) {
              const file = droppedFiles[i] as any;
              const path = file.path || file.name;
              
              try {
                  const info = await stat(path);
                  if (info.isDirectory) {
                      const newFiles = await scanDirectory(path, path);
                      let addedCount = 0;
                      for (const nf of newFiles) {
                          if (!files.value.some(f => f.originalPath === nf.originalPath)) {
                              files.value.push(nf);
                              addedCount++;
                          }
                      }
                      addLog(`已递归添加目录: ${path} (${addedCount} 文件)`, 'success');
                  } else {
                      // It's a file
                      const name = path.split(/[\\/]/).pop() || path;
                      const validExtensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.gif'];
                      if (validExtensions.some(ext => name.toLowerCase().endsWith(ext))) {
                          if (!files.value.some(f => f.originalPath === path)) {
                              files.value.push({
                                  originalPath: path,
                                  relativePath: name,
                                  name,
                                  status: 'pending'
                              });
                              addLog(`已添加文件: ${name}`, 'success');
                          }
                      }
                  }
              } catch (e) {
                  addLog(`无法读取拖入路径: ${path}`, 'error');
              }
          }
      }
  }
};

const removeFile = (index: number) => {
    files.value.splice(index, 1);
};

const clearFiles = () => {
    files.value = [];
    logs.value = [];
};

const startProcess = async () => {
    if (files.value.length === 0) return;
    
    isProcessing.value = true;
    logs.value = [];
    progress.value = { current: 0, total: files.value.length };
    
    // Reset statuses
    files.value.forEach(f => f.status = 'pending');

    for (let i = 0; i < files.value.length; i++) {
        const file = files.value[i];
        file.status = 'processing';
        progress.value.current = i + 1;
        
        try {
            addLog(`正在处理: ${file.name}`, 'info');
            
            // Determine Output Path
            let targetFilename = '';
            
            // Remove extension from relative path for the new filename
            const lastDot = file.relativePath.lastIndexOf('.');
            const relativeNoExt = lastDot !== -1 ? file.relativePath.substring(0, lastDot) : file.relativePath;
            targetFilename = relativeNoExt + '.apng'; // This might contain slashes if relativePath has subdirs
            
            if (config.outputFolder) {
                // If output folder is set, we join it with the relative structure
                // But join() handles slashes.
                // We need to ensure the subdirectories exist.
                
                // Construct full target path
                const fullTargetPath = await join(config.outputFolder, targetFilename);
                
                // Extract the directory part of the target path to ensure it exists
                // We can't use node's path.dirname easily.
                // Hack: remove the filename from the end
                const pathSep = fullTargetPath.includes('\\') ? '\\' : '/';
                const targetDirPart = fullTargetPath.substring(0, fullTargetPath.lastIndexOf(pathSep));
                
                if (targetDirPart && targetDirPart !== config.outputFolder) {
                    await mkdir(targetDirPart, { recursive: true });
                }
                
                // Re-assign for FFmpeg
                // ffmpeg needs the full path
                file.relativePath = fullTargetPath; // Storing the result path temporarily here or just use a local var
            } else {
                // In-place export
                // targetFilename is just relative.
                // If relativePath has subdirs, and originalPath was absolute...
                // Wait, if in-place, we just swap extension of originalPath
                const dotIndex = file.originalPath.lastIndexOf('.');
                const outputPath = (dotIndex !== -1 ? file.originalPath.substring(0, dotIndex) : file.originalPath) + '.apng';
                file.relativePath = outputPath; // abuse property
            }

            const finalOutputPath = config.outputFolder 
                ? await join(config.outputFolder, targetFilename)
                : (file.originalPath.substring(0, file.originalPath.lastIndexOf('.')) + '.apng');

            // Ensure dir exists again just to be safe for all cases
             if (config.outputFolder) {
                 const sep = finalOutputPath.includes('\\') ? '\\' : '/';
                 const dir = finalOutputPath.substring(0, finalOutputPath.lastIndexOf(sep));
                 await mkdir(dir, { recursive: true });
             }

            // Construct Filters
            const filters: string[] = [];
            filters.push(`fps=${config.fps}`);
            
            if (!config.keepOriginalResolution && config.width > 0) {
                filters.push(`scale=${config.width}:-1:flags=lanczos`);
            }
            
            if (config.mpdecimate) {
                filters.push('mpdecimate');
            }
            
            const args = [
                '-y',
                '-v', 'error',
                '-i', file.originalPath,
                '-vf', filters.join(','),
                '-c:v', 'apng',
                '-plays', config.loop.toString(),
                '-pred', config.pred.toString(),
                '-compression_level', config.compressionLevel.toString(),
                '-pix_fmt', config.pixelFormat,
                '-f', 'apng',
                finalOutputPath
            ];
            
            addLog(`Command: ffmpeg ... ${finalOutputPath}`, 'info');

            const command = Command.create('ffmpeg', args);
            const output = await command.execute();

            if (output.code === 0) {
                file.status = 'done';
                addLog(`转换成功`, 'success');
            } else {
                file.status = 'error';
                addLog(`转换失败: ${output.stderr}`, 'error');
            }

        } catch (e: any) {
            file.status = 'error';
            addLog(`异常: ${e.message}`, 'error');
        }
    }
    
    isProcessing.value = false;
    addLog('所有任务完成', 'success');
};

const progressPercentage = computed(() => {
  if (progress.value.total === 0) return 0;
  return Math.round((progress.value.current / progress.value.total) * 100);
});

</script>

<template>
  <div class="flex flex-col gap-4 max-w-6xl mx-auto h-full">
    
    <!-- Hero / Title -->
    <div class="flex items-end justify-between shrink-0">
      <div class="space-y-1">
        <h2 class="text-xl font-bold text-white tracking-tight">视频转 APNG</h2>
        <p class="text-zinc-400 text-xs">基于 FFmpeg 将视频转换为高画质动态 PNG，支持去重与无损压缩</p>
      </div>
      
      <div v-if="isProcessing" class="flex items-center gap-3 bg-zinc-900/50 px-3 py-1.5 rounded-lg border border-white/5 backdrop-blur">
         <span class="text-[10px] font-mono text-primary">{{ progress.current }} / {{ progress.total }}</span>
         <div class="w-24 h-1 bg-zinc-800 rounded-full overflow-hidden">
             <div class="h-full bg-primary transition-all duration-300 ease-out" :style="{ width: `${progressPercentage}%` }"></div>
         </div>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-12 gap-4 h-full min-h-0">
      
      <!-- Left: Configuration & File List -->
      <div class="lg:col-span-7 flex flex-col gap-4 h-full min-h-0 relative">
        <div class="flex-1 overflow-y-auto pr-2 custom-scrollbar space-y-4">
            
            <!-- File List Card -->
            <section class="bg-zinc-900/40 border border-white/5 rounded-xl p-4 flex flex-col gap-3 min-h-[160px]">
                <div class="flex items-center justify-between">
                    <h3 class="text-xs font-semibold text-zinc-200 flex items-center gap-2">
                        <Film class="w-3.5 h-3.5 text-zinc-400" />
                        待处理文件
                    </h3>
                    <div class="flex gap-2">
                         <button @click="clearFiles" v-if="files.length > 0" class="p-1.5 hover:bg-red-500/10 hover:text-red-400 text-zinc-500 rounded-lg transition-colors" title="清空列表">
                             <Trash2 class="w-3.5 h-3.5" />
                         </button>
                         <button @click="addFiles" class="flex items-center gap-1.5 px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg text-xs transition-colors border border-white/5">
                             <Plus class="w-3.5 h-3.5" />
                             <span>文件</span>
                         </button>
                         <button @click="addFolder" class="flex items-center gap-1.5 px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg text-xs transition-colors border border-white/5">
                             <Folder class="w-3.5 h-3.5" />
                             <span>文件夹</span>
                         </button>
                    </div>
                </div>

                <!-- Drop Zone / List -->
                <div 
                    class="flex-1 bg-black/20 rounded-lg border overflow-hidden flex flex-col transition-all"
                    :class="isDragging === 'files' ? 'border-primary bg-primary/10' : 'border-white/5'"
                    @dragover.prevent="isDragging = 'files'"
                    @dragleave.prevent="isDragging = null"
                    @drop.prevent="handleDrop($event, 'files')"
                >
                    <div v-if="files.length === 0" class="flex-1 flex flex-col items-center justify-center text-zinc-600 space-y-2 py-8">
                        <Upload class="w-8 h-8 opacity-20" />
                        <span class="text-[10px]">拖入视频文件或文件夹</span>
                    </div>
                    <div v-else class="flex-1 overflow-y-auto custom-scrollbar p-1 space-y-1">
                        <div v-for="(file, idx) in files" :key="file.originalPath" class="group flex items-center gap-3 p-2 rounded hover:bg-white/5 transition-colors">
                            <FileVideo class="w-4 h-4 text-zinc-500 shrink-0" />
                            <div class="flex-1 min-w-0 flex flex-col">
                                <div class="text-xs text-zinc-300 truncate font-mono">{{ file.name }}</div>
                                <div class="text-[10px] text-zinc-600 truncate font-mono">{{ file.relativePath }}</div>
                            </div>
                            
                            <!-- Status -->
                            <div class="shrink-0">
                                <Loader2 v-if="file.status === 'processing'" class="w-3.5 h-3.5 animate-spin text-primary" />
                                <CheckCircle2 v-else-if="file.status === 'done'" class="w-3.5 h-3.5 text-emerald-500" />
                                <AlertCircle v-else-if="file.status === 'error'" class="w-3.5 h-3.5 text-red-500" />
                                <button v-else @click="removeFile(idx)" class="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-500/20 text-zinc-500 hover:text-red-400 rounded transition-all">
                                    <Trash2 class="w-3 h-3" />
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </section>
            
            <!-- Output Directory Card -->
             <section class="group relative bg-zinc-900/40 border border-white/5 hover:border-white/10 rounded-xl p-1 transition-all">
                  <div class="absolute inset-0 bg-gradient-to-b from-white/5 to-transparent opacity-0 group-hover:opacity-100 rounded-xl transition-opacity pointer-events-none"></div>
                  
                  <div class="relative p-3 space-y-3">
                     <!-- Output Input -->
                     <div 
                       class="relative overflow-hidden bg-black/20 border rounded-lg p-1 transition-all group/output flex gap-3 items-center"
                       :class="isDragging === 'output' ? 'border-primary bg-primary/10' : 'border-white/5 hover:border-primary/30 hover:bg-black/30'"
                       @dragover.prevent="isDragging = 'output'"
                       @dragleave.prevent="isDragging = null"
                       @drop.prevent="handleDrop($event, 'output')"
                     >
                        <button 
                          @click="selectOutputFolder"
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
                              placeholder="留空则保存到源文件所在目录..." 
                              class="w-full bg-transparent border-none p-0.5 text-xs text-zinc-200 placeholder-zinc-600 font-mono focus:ring-0 focus:outline-none truncate"
                            />
                        </div>
    
                        <div class="pr-2 text-zinc-600">
                            <CheckCircle2 v-if="config.outputFolder" class="w-3.5 h-3.5 text-emerald-500/80" />
                            <ChevronRight v-else class="w-3.5 h-3.5 opacity-50" />
                        </div>
                     </div>
                  </div>
             </section>

            <!-- Settings Card -->
            <section class="bg-zinc-900/40 border border-white/5 rounded-xl p-4 space-y-4">
                 <div class="flex items-center gap-2 mb-2">
                    <Settings2 class="w-3.5 h-3.5 text-zinc-400" />
                    <h3 class="text-xs font-semibold text-zinc-200">转换参数</h3>
                 </div>

                 <div class="grid grid-cols-2 gap-4">
                     <!-- FPS -->
                     <div class="space-y-1.5">
                        <label class="text-[9px] text-zinc-500 uppercase font-bold tracking-wider flex items-center gap-1">
                            <MonitorPlay class="w-3 h-3" /> 帧率 (FPS)
                        </label>
                        <div class="flex items-center gap-2 bg-black/20 rounded-lg p-1 border border-white/5">
                            <input type="range" min="1" max="60" v-model.number="config.fps" class="flex-1 h-1.5 ml-2 bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-primary" />
                            <input type="number" v-model.number="config.fps" class="w-12 bg-transparent text-center text-xs text-white font-mono focus:outline-none" />
                        </div>
                     </div>

                     <!-- Loop -->
                     <div class="space-y-1.5">
                        <label class="text-[9px] text-zinc-500 uppercase font-bold tracking-wider flex items-center gap-1">
                            <Repeat class="w-3 h-3" /> 循环次数
                        </label>
                         <div class="flex items-center gap-2 bg-black/20 rounded-lg p-1 border border-white/5">
                            <input type="number" v-model.number="config.loop" min="0" placeholder="0 = 无限" class="w-full bg-transparent px-2 py-1 text-xs text-white font-mono focus:outline-none placeholder-zinc-600" />
                             <span class="text-[10px] text-zinc-500 pr-2 whitespace-nowrap">0 = ∞</span>
                        </div>
                     </div>
                 </div>

                 <!-- Resolution -->
                 <div class="space-y-2 pt-2 border-t border-white/5">
                     <div class="flex items-center justify-between">
                        <label class="text-[9px] text-zinc-500 uppercase font-bold tracking-wider flex items-center gap-1">
                            <Scissors class="w-3 h-3" /> 分辨率控制
                        </label>
                        <label class="flex items-center gap-2 cursor-pointer select-none">
                             <input type="checkbox" v-model="config.keepOriginalResolution" class="rounded bg-zinc-800 border-zinc-700 text-primary focus:ring-primary/50 w-3.5 h-3.5" />
                             <span class="text-[10px] text-zinc-400">保持原始分辨率</span>
                        </label>
                     </div>
                     
                     <div v-if="!config.keepOriginalResolution" class="animate-fade-in flex items-center gap-3 bg-black/20 rounded-lg p-2 border border-white/5">
                         <span class="text-xs text-zinc-400">宽度 (px):</span>
                         <input type="number" v-model.number="config.width" placeholder="例如: 800" class="flex-1 bg-zinc-900/50 border border-zinc-700 rounded px-2 py-1 text-xs text-white focus:border-primary outline-none font-mono" />
                         <span class="text-[10px] text-zinc-500 italic">高度自动适应比例</span>
                     </div>
                 </div>

                 <!-- Advanced -->
                 <div class="grid grid-cols-2 gap-4 pt-2 border-t border-white/5">
                     <!-- Compression -->
                     <div class="space-y-1.5">
                         <label class="text-[9px] text-zinc-500 uppercase font-bold tracking-wider flex items-center gap-1">
                            <Minimize2 class="w-3 h-3" /> 压缩等级 (0-9)
                         </label>
                         <div class="flex items-center gap-2">
                             <input type="range" min="0" max="9" v-model.number="config.compressionLevel" class="flex-1 h-1.5 bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-primary" />
                             <span class="text-xs font-mono text-zinc-300 w-4 text-center">{{ config.compressionLevel }}</span>
                         </div>
                     </div>

                     <!-- Pixel Format -->
                     <div class="space-y-1.5">
                         <label class="text-[9px] text-zinc-500 uppercase font-bold tracking-wider">像素格式</label>
                         <select v-model="config.pixelFormat" class="w-full bg-black/20 border border-white/5 rounded-lg px-2 py-1 text-xs text-zinc-300 outline-none">
                             <option value="rgba">RGBA (透明支持)</option>
                             <option value="rgb24">RGB24 (无透明)</option>
                             <option value="yuva420p">YUVA420P</option>
                         </select>
                     </div>
                 </div>
                 
                 <div class="pt-2">
                     <label class="flex items-center gap-2 cursor-pointer select-none bg-black/20 p-2 rounded-lg border border-white/5 hover:bg-black/30 transition-colors">
                         <input type="checkbox" v-model="config.mpdecimate" class="rounded bg-zinc-800 border-zinc-700 text-primary focus:ring-primary/50 w-3.5 h-3.5" />
                         <div class="flex flex-col">
                             <span class="text-xs font-medium text-zinc-300">去除重复帧 (Mpdecimate)</span>
                             <span class="text-[10px] text-zinc-500">自动移除静态帧以减小体积</span>
                         </div>
                     </label>
                 </div>

            </section>
        </div>

        <!-- Run Button -->
        <button 
          @click="startProcess" 
          :disabled="isProcessing || files.length === 0"
          class="w-full mt-auto group relative overflow-hidden py-4 rounded-xl font-bold text-white shadow-[0_0_20px_rgba(99,102,241,0.3)] transition-all active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed disabled:shadow-none hover:shadow-[0_0_30px_rgba(99,102,241,0.5)] border border-primary/20"
          :class="isProcessing ? 'bg-zinc-800' : 'bg-gradient-to-r from-violet-600 to-indigo-600'"
        >
          <div class="relative z-10 flex items-center justify-center gap-3">
             <Loader2 v-if="isProcessing" class="w-5 h-5 animate-spin" />
             <Play v-else class="w-5 h-5 fill-current" />
             <span class="text-base tracking-wide">{{ isProcessing ? 'Processing...' : '开始转换' }}</span>
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
                  <span>FFMPEG OUTPUT</span>
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