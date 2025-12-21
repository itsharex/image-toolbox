<script setup lang="ts">
import { ref, reactive } from 'vue';
import { Command, open as openUrl } from '@tauri-apps/plugin-shell';
import { open as openDialog } from '@tauri-apps/plugin-dialog';
import { tempDir, localDataDir } from '@tauri-apps/api/path';
import { 
  Download, Terminal, 
  Info, Github, Package, 
  Cpu, Monitor, ShieldCheck,
  RefreshCw, FileCode, X, Folder
} from 'lucide-vue-next';

// --- State ---
const ffmpegStatus = ref<'unknown' | 'installed' | 'missing'>('unknown');
const ffmpegVersion = ref('');
const appVersion = '0.1.0';
const isChecking = ref(false);
const logs = ref<string[]>([]);

// Install Modal State
const showInstallModal = ref(false);
const isInstalling = ref(false);
const installConfig = reactive({
    source: 'official' as 'official' | 'mirror',
    cachePath: '',
    installPath: '',
    pathScope: 'User' as 'User' | 'Machine'
});

// Sources
const SOURCES = {
    official: 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-git-full.7z',
    mirror: 'https://assets.hcaor.org/mirror/ffmpeg/ffmpeg-git-full.7z'
};

// --- Actions ---

const addLog = (msg: string) => {
  logs.value.push(`[${new Date().toLocaleTimeString()}] ${msg}`);
};

const checkFFmpeg = async () => {
  isChecking.value = true;
  addLog('正在检查 PATH 中的 FFmpeg...');
  
  // Method 1: Direct Execution
  try {
    const cmd = Command.create('ffmpeg', ['-version']);
    const out = await cmd.execute();
    if (out.code === 0) {
      ffmpegStatus.value = 'installed';
      const firstLine = out.stdout.split('\n')[0];
      ffmpegVersion.value = firstLine;
      addLog(`[Direct] 已检测到 FFmpeg: ${firstLine}`);
      return; 
    } else {
        addLog(`[Direct] 检查失败 (Code ${out.code})`);
    }
  } catch (e) {
    addLog(`[Direct] 执行异常: ${e}`);
  }

  // Method 2: PowerShell Lookup (Fallback)
  addLog('尝试通过 PowerShell 查找...');
  try {
      const psCmd = Command.create('powershell', ['-Command', 'Get-Command ffmpeg | Select-Object -ExpandProperty Source']);
      const psOut = await psCmd.execute();
      if (psOut.code === 0 && psOut.stdout.trim()) {
          const path = psOut.stdout.trim();
          ffmpegStatus.value = 'installed';
          ffmpegVersion.value = `Detected at: ${path}`;
          addLog(`[PowerShell] 发现 FFmpeg 路径: ${path}`);
          addLog('提示: 虽然找到了路径，但在当前应用环境中无法直接调用，可能需要重启应用更新环境变量。');
      } else {
          ffmpegStatus.value = 'missing';
          addLog('PowerShell 也未找到 ffmpeg。');
      }
  } catch (e) {
      ffmpegStatus.value = 'missing';
      addLog(`[PowerShell] 查找失败: ${e}`);
  } finally {
    isChecking.value = false;
  }
};

const openInstallModal = async () => {
    if (!installConfig.cachePath) {
        installConfig.cachePath = await tempDir();
    }
    if (!installConfig.installPath) {
        installConfig.installPath = await localDataDir(); 
    }
    showInstallModal.value = true;
};

const selectPath = async (target: 'cache' | 'install') => {
    const selected = await openDialog({
        directory: true,
        multiple: false,
        title: target === 'cache' ? '选择缓存目录' : '选择安装目录'
    });
    if (selected) {
        if (target === 'cache') installConfig.cachePath = selected as string;
        else installConfig.installPath = selected as string;
    }
};

const startInstallation = async () => {
    isInstalling.value = true;
    showInstallModal.value = false;
    addLog('--- 开始安装流程 ---');
    
    const url = SOURCES[installConfig.source];
    // Safe escaping for PowerShell
    const cacheDir = installConfig.cachePath.split('\\').join('\\\\');
    const installParentDir = installConfig.installPath.split('\\').join('\\\\');
    const scope = installConfig.pathScope;
    
    const sevenZipUrl = "https://assets.hcaor.org/mirror/7zip/7za.exe";

    const psScript = `
        $ErrorActionPreference = "Stop"
        
        $url = "${url}"
        $7zUrl = "${sevenZipUrl}"
        $cacheDir = "${cacheDir}"
        $installBase = "${installParentDir}"
        $scope = "${scope}"
        
        $7zExe = "$cacheDir\\7za.exe"
        $archivePath = "$cacheDir\\ffmpeg_installer.7z"
        $finalInstallDir = "$installBase\\ffmpeg_tool"

        # 1. Download 7za if not exists
        if (-not (Test-Path $7zExe)) {
            Write-Output "Downloading 7-Zip tool..."
            Invoke-WebRequest -Uri $7zUrl -OutFile $7zExe
        }

        # 2. Download FFmpeg
        Write-Output "Downloading FFmpeg from $url..."
        Invoke-WebRequest -Uri $url -OutFile $archivePath

        # 3. Extract
        Write-Output "Extracting to $finalInstallDir..."
        if (Test-Path $finalInstallDir) { Remove-Item -Recurse -Force $finalInstallDir }
        New-Item -ItemType Directory -Force -Path $finalInstallDir | Out-Null
        
        # Use 7zr to extract
        $proc = Start-Process -FilePath $7zExe -ArgumentList "x", "$archivePath", "-o$finalInstallDir", "-y" -Wait -PassThru
        if ($proc.ExitCode -ne 0) {
            Write-Error "7-Zip extraction failed with code $($proc.ExitCode)"
        }

        # 4. Find bin folder
        $binPath = Get-ChildItem -Path $finalInstallDir -Recurse -Filter "ffmpeg.exe" | Select-Object -ExpandProperty DirectoryName -First 1
        
        if ($binPath) {
            Write-Output "Found binary at: $binPath"
            
            # 5. Update PATH
            $currentPath = [Environment]::GetEnvironmentVariable("Path", $scope)
            if ($currentPath -notlike "*$binPath*") {
                Write-Output "Adding to $scope PATH..."
                [Environment]::SetEnvironmentVariable("Path", $currentPath + ";$binPath", $scope)
                Write-Output "SUCCESS: Added to PATH."
            } else {
                Write-Output "PATH already contains this directory."
            }
        } else {
            Write-Error "Could not find ffmpeg.exe after extraction."
        }
    `;

    try {
        const cmd = Command.create('powershell', ['-Command', psScript]);
        
        cmd.on('close', data => {
            isInstalling.value = false;
            if (data.code === 0) {
                addLog('安装成功！请重启应用以生效环境变量。');
                checkFFmpeg();
            } else {
                addLog(`安装脚本退出，代码: ${data.code}`);
            }
        });
        cmd.on('error', error => {
            isInstalling.value = false;
            addLog(`脚本错误: ${error}`);
        });
        
        const child = await cmd.spawn();
        addLog(`后台进程已启动 (PID: ${child.pid})，请关注日志...`);
        
    } catch (e) {
        isInstalling.value = false;
        addLog(`启动失败: ${e}`);
    }
};

const addToPath = async () => {
  addLog('正在将当前应用添加至 PATH...');
  const psScript = `
    $currentPath = [System.Diagnostics.Process]::GetCurrentProcess().MainModule.FileName
    $dir = [System.IO.Path]::GetDirectoryName($currentPath)
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    
    if ($userPath -notlike "*$dir*") {
        [Environment]::SetEnvironmentVariable("Path", $userPath + ";$dir", "User")
        Write-Output "ADDED: $dir"
    } else {
        Write-Output "EXISTS: Path already present."
    }
  `;
  try {
    const cmd = Command.create('powershell', ['-Command', psScript]);
    const out = await cmd.execute();
    if (out.code === 0) addLog(`操作结果: ${out.stdout.trim()}`);
    else addLog(`失败: ${out.stderr}`);
  } catch (e) {
    addLog(`执行错误: ${e}`);
  }
};

const openRepo = () => {
  openUrl('https://github.com/EIHRTeam/image-toolbox'); 
};

// Initial check
checkFFmpeg();
</script>

<template>
  <div class="max-w-4xl mx-auto space-y-8 pb-10 relative">
    
    <!-- Hero -->
    <div class="space-y-1">
       <h2 class="text-2xl font-bold text-white tracking-tight">系统设置</h2>
       <p class="text-zinc-400 text-sm">管理环境依赖与应用更新</p>
    </div>

    <!-- Environment Section -->
    <section class="space-y-4">
        <h3 class="text-sm font-bold text-zinc-500 uppercase tracking-wider flex items-center gap-2">
            <Terminal class="w-4 h-4" /> 环境依赖 (Environment)
        </h3>
        
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <!-- FFmpeg Card -->
            <div class="bg-zinc-900/40 border border-white/5 rounded-xl p-5 space-y-4">
                <div class="flex items-start justify-between">
                    <div class="flex items-center gap-3">
                        <div class="p-2 rounded-lg bg-zinc-800 text-zinc-300">
                            <FileCode class="w-5 h-5" />
                        </div>
                        <div>
                            <div class="font-bold text-zinc-200">FFmpeg</div>
                            <div class="text-xs text-zinc-500">视频/图片处理核心组件</div>
                        </div>
                    </div>
                    <div v-if="ffmpegStatus === 'installed'" class="px-2 py-1 rounded-md bg-emerald-500/10 text-emerald-500 text-[10px] font-bold border border-emerald-500/20">
                        INSTALLED
                    </div>
                    <div v-else-if="ffmpegStatus === 'missing'" class="px-2 py-1 rounded-md bg-rose-500/10 text-rose-500 text-[10px] font-bold border border-rose-500/20">
                        MISSING
                    </div>
                </div>
                
                <div class="h-px bg-white/5"></div>
                
                <div v-if="ffmpegStatus === 'installed'" class="text-xs font-mono text-zinc-400 truncate">
                    {{ ffmpegVersion }}
                </div>
                <div v-else class="text-xs text-zinc-500">
                    未检测到 FFmpeg，图片处理功能将不可用。
                </div>

                <div class="flex gap-2 pt-2">
                    <button @click="checkFFmpeg" class="flex-1 px-3 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-xs font-medium text-zinc-200 transition-colors flex items-center justify-center gap-2">
                        <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': isChecking }" /> 检查
                    </button>
                    <button @click="openInstallModal" :disabled="isInstalling" class="flex-1 px-3 py-2 bg-primary/10 hover:bg-primary/20 text-primary border border-primary/20 rounded-lg text-xs font-medium transition-colors flex items-center justify-center gap-2 disabled:opacity-50">
                        <Download class="w-3.5 h-3.5" /> {{ isInstalling ? '安装中...' : '安装 FFmpeg' }}
                    </button>
                </div>
            </div>

            <!-- Path Card -->
            <div class="bg-zinc-900/40 border border-white/5 rounded-xl p-5 space-y-4">
                <div class="flex items-start justify-between">
                    <div class="flex items-center gap-3">
                        <div class="p-2 rounded-lg bg-zinc-800 text-zinc-300">
                            <Package class="w-5 h-5" />
                        </div>
                        <div>
                            <div class="font-bold text-zinc-200">CLI Integration</div>
                            <div class="text-xs text-zinc-500">添加应用至系统 PATH</div>
                        </div>
                    </div>
                </div>
                
                <div class="h-px bg-white/5"></div>
                
                <p class="text-xs text-zinc-500">
                    将 Image Toolbox 添加到用户环境变量中，以便在任意终端通过命令行启动。
                </p>

                <div class="pt-2">
                     <button @click="addToPath" class="w-full px-3 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-xs font-medium text-zinc-200 transition-colors flex items-center justify-center gap-2">
                        <Terminal class="w-3.5 h-3.5" /> 添加至 User PATH
                    </button>
                </div>
            </div>
        </div>
    </section>

    <!-- About Section -->
    <section class="space-y-4">
        <h3 class="text-sm font-bold text-zinc-500 uppercase tracking-wider flex items-center gap-2">
            <Info class="w-4 h-4" /> 关于 (About)
        </h3>
        
        <div class="bg-zinc-900/40 border border-white/5 rounded-xl p-6 relative overflow-hidden">
            <div class="absolute top-0 right-0 p-32 bg-primary/5 rounded-full blur-3xl -mr-16 -mt-16 pointer-events-none"></div>
            
            <div class="relative z-10 flex flex-col md:flex-row gap-8 items-center md:items-start">
                <!-- Info -->
                <div class="space-y-4 flex-1">
                     <div>
                         <h1 class="text-xl font-bold text-white">Image Toolbox</h1>
                         <p class="text-sm text-zinc-400 mt-1">Version {{ appVersion }}</p>
                     </div>
                     
                     <div class="flex gap-4 text-xs text-zinc-500 font-mono">
                         <div class="flex items-center gap-1.5">
                             <Monitor class="w-3.5 h-3.5" />
                             <span>Tauri v2</span>
                         </div>
                         <div class="flex items-center gap-1.5">
                             <Cpu class="w-3.5 h-3.5" />
                             <span>Rust Backend</span>
                         </div>
                     </div>

                     <div class="flex gap-3 pt-2">
                         <button @click="openRepo" class="px-4 py-2 bg-white/10 hover:bg-white/20 text-white rounded-lg text-xs font-bold transition-colors flex items-center gap-2">
                             <Github class="w-4 h-4" />
                             GitHub Repo
                         </button>
                         <button class="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg text-xs font-bold transition-colors flex items-center gap-2">
                             <ShieldCheck class="w-4 h-4" />
                             Check Updates
                         </button>
                     </div>
                </div>
            </div>
        </div>
    </section>

    <!-- Logs Console -->
    <div class="bg-black/40 rounded-xl border border-white/5 p-4 h-48 overflow-y-auto font-mono text-[10px] text-zinc-500 space-y-1">
        <div v-for="(log, i) in logs" :key="i">{{ log }}</div>
        <div v-if="logs.length === 0" class="text-center italic opacity-50 pt-10">操作日志将显示在这里...</div>
    </div>

    <!-- INSTALLATION MODAL -->
    <Teleport to="body">
      <div v-if="showInstallModal" class="fixed inset-0 z-50 flex items-center justify-center p-4">
          <!-- Backdrop -->
          <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" @click="showInstallModal = false"></div>
          
          <!-- Content -->
          <div class="relative bg-zinc-900 border border-white/10 rounded-2xl w-full max-w-lg shadow-2xl p-6 space-y-6 animate-fade-in">
              <div class="flex justify-between items-start">
                  <div>
                      <h3 class="text-lg font-bold text-white">安装 FFmpeg</h3>
                      <p class="text-xs text-zinc-400 mt-1">配置下载源与安装路径</p>
                  </div>
                  <button @click="showInstallModal = false" class="text-zinc-500 hover:text-white transition-colors">
                      <X class="w-5 h-5" />
                  </button>
              </div>

              <div class="space-y-4">
                  <!-- Source -->
                  <div class="space-y-2">
                      <label class="text-[11px] uppercase font-bold text-zinc-500 tracking-wider">下载源 (Download Source)</label>
                      <div class="grid grid-cols-2 gap-3">
                          <label class="flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-all" 
                              :class="installConfig.source === 'official' ? 'bg-primary/10 border-primary text-white' : 'bg-black/20 border-white/5 text-zinc-400 hover:bg-black/40'">
                              <input type="radio" value="official" v-model="installConfig.source" class="hidden">
                              <div class="flex flex-col">
                                  <span class="text-xs font-bold">官方源 (Gyan.dev)</span>
                                  <span class="text-[10px] opacity-70">国外节点，可能较慢</span>
                              </div>
                          </label>
                          <label class="flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-all" 
                              :class="installConfig.source === 'mirror' ? 'bg-primary/10 border-primary text-white' : 'bg-black/20 border-white/5 text-zinc-400 hover:bg-black/40'">
                              <input type="radio" value="mirror" v-model="installConfig.source" class="hidden">
                              <div class="flex flex-col">
                                  <span class="text-xs font-bold">Cloudflare 镜像</span>
                                  <span class="text-[10px] opacity-70">国内推荐，速度快</span>
                              </div>
                          </label>
                      </div>
                  </div>

                  <!-- Paths -->
                  <div class="space-y-3">
                      <div class="space-y-1">
                          <label class="text-[11px] uppercase font-bold text-zinc-500 tracking-wider">缓存路径 (Cache)</label>
                          <div class="flex gap-2">
                              <input type="text" v-model="installConfig.cachePath" class="flex-1 bg-black/20 border border-white/10 rounded-lg px-3 py-2 text-xs text-zinc-300 font-mono focus:border-primary/50 outline-none" />
                              <button @click="selectPath('cache')" class="p-2 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-zinc-400 transition-colors">
                                  <Folder class="w-4 h-4" />
                              </button>
                          </div>
                      </div>
                      <div class="space-y-1">
                          <label class="text-[11px] uppercase font-bold text-zinc-500 tracking-wider">安装路径 (Install Location)</label>
                          <div class="flex gap-2">
                              <input type="text" v-model="installConfig.installPath" class="flex-1 bg-black/20 border border-white/10 rounded-lg px-3 py-2 text-xs text-zinc-300 font-mono focus:border-primary/50 outline-none" />
                              <button @click="selectPath('install')" class="p-2 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-zinc-400 transition-colors">
                                  <Folder class="w-4 h-4" />
                              </button>
                          </div>
                      </div>
                  </div>

                  <!-- Scope -->
                  <div class="space-y-2">
                      <label class="text-[11px] uppercase font-bold text-zinc-500 tracking-wider">环境变量 (PATH Scope)</label>
                      <div class="flex gap-4">
                          <label class="flex items-center gap-2 text-xs text-zinc-300 cursor-pointer">
                              <input type="radio" value="User" v-model="installConfig.pathScope" class="text-primary bg-zinc-800 border-zinc-600 focus:ring-primary">
                              User (推荐，无需权限)
                          </label>
                          <label class="flex items-center gap-2 text-xs text-zinc-300 cursor-pointer">
                              <input type="radio" value="Machine" v-model="installConfig.pathScope" class="text-primary bg-zinc-800 border-zinc-600 focus:ring-primary">
                              System (需管理员权限)
                          </label>
                      </div>
                  </div>
              </div>

              <!-- Footer -->
              <div class="flex justify-end gap-3 pt-2">
                  <button @click="showInstallModal = false" class="px-4 py-2 text-xs font-bold text-zinc-400 hover:text-white transition-colors">
                      取消
                  </button>
                  <button @click="startInstallation" class="px-6 py-2 bg-primary hover:bg-primary-hover text-white rounded-xl text-xs font-bold shadow-lg shadow-primary/20 transition-all flex items-center gap-2">
                      <Download class="w-3.5 h-3.5" />
                      开始下载并安装
                  </button>
              </div>
          </div>
      </div>
    </Teleport>

  </div>
</template>
