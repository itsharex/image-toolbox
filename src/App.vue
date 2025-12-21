<script setup lang="ts">
import { ref } from 'vue';
import { Image, Settings as SettingsIcon, Layers, Box } from 'lucide-vue-next';
import ImageCompressor from './components/ImageCompressor.vue';
import Settings from './components/Settings.vue';
import logoUrl from './assets/logo.png'; // Make sure to put the file here!

const activeTab = ref('compressor');

const navItems = [
  { id: 'compressor', label: '图片压缩', icon: Image },
  { id: 'batch', label: '批量重命名', icon: Layers, disabled: true },
  { id: 'settings', label: '设置', icon: SettingsIcon },
];
</script>

<template>
  <div class="flex h-screen w-screen bg-background text-zinc-100 font-sans selection:bg-primary/30 selection:text-white overflow-hidden">
    
    <!-- Background Gradient Mesh -->
    <div class="fixed inset-0 pointer-events-none z-0">
       <div class="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-primary/5 rounded-full blur-[120px] opacity-40"></div>
       <div class="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-purple-600/5 rounded-full blur-[120px] opacity-40"></div>
    </div>

    <!-- Sidebar -->
    <aside class="w-[260px] flex flex-col border-r border-white/5 bg-zinc-900/50 backdrop-blur-2xl z-20 relative">
      <!-- Logo Area -->
      <div data-tauri-drag-region class="p-6 pb-8 shrink-0">
        <div class="flex items-center gap-3.5 px-1">
          <div class="relative group">
            <div class="absolute inset-0 bg-primary/40 blur-md rounded-xl opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
            <div class="w-9 h-9 relative rounded-xl bg-zinc-900/50 border border-white/10 flex items-center justify-center shadow-inner overflow-hidden">
               <img :src="logoUrl" class="w-full h-full object-cover" alt="Logo" />
            </div>
          </div>
          <div class="flex flex-col">
            <h1 class="font-bold text-lg tracking-tight text-white leading-none">Image Toolbox</h1>
            <span class="text-[10px] text-zinc-500 font-medium tracking-widest uppercase mt-1">v0.1.0</span>
          </div>
        </div>
      </div>

      <!-- Navigation -->
      <nav class="flex-1 px-4 space-y-1.5 overflow-y-auto">
        <div v-for="section in ['工具', '系统']" :key="section" class="mb-2 mt-4 px-3 first:mt-0">
             <span class="text-[10px] uppercase tracking-wider text-zinc-600 font-semibold">{{ section }}</span>
        </div>

        <button 
          v-for="item in navItems" 
          :key="item.id"
          @click="!item.disabled && (activeTab = item.id)"
          :disabled="item.disabled"
          class="relative w-full group flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 outline-none focus-visible:ring-2 focus-visible:ring-primary/50"
          :class="[
            activeTab === item.id 
              ? 'bg-primary/10 text-white' 
              : 'text-zinc-400 hover:bg-white/5 hover:text-zinc-200',
            item.disabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'
          ]"
        >
           <component 
            :is="item.icon" 
            class="w-4.5 h-4.5 transition-colors duration-200"
            :class="activeTab === item.id ? 'text-primary' : 'text-zinc-500 group-hover:text-zinc-300'"
            stroke-width="2"
           />
           <span class="text-sm font-medium">{{ item.label }}</span>
           
           <!-- Active Indicator -->
           <div v-if="activeTab === item.id" class="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-4 bg-primary rounded-r-full shadow-[0_0_8px_rgba(99,102,241,0.5)]"></div>
        </button>
      </nav>

      <!-- Footer / User -->
      <div class="p-4 border-t border-white/5">
         <div class="flex items-center gap-3 p-2 rounded-lg bg-white/5 border border-white/5">
             <div class="w-8 h-8 rounded-md bg-gradient-to-tr from-zinc-700 to-zinc-600 flex items-center justify-center text-xs font-bold text-white shadow-sm">
                 <Box class="w-4 h-4" />
             </div>
             <div class="flex flex-col overflow-hidden">
                 <span class="text-xs font-medium text-zinc-200 truncate">Image Engine</span>
                 <span class="text-[10px] text-zinc-500 truncate">Standard User</span>
             </div>
         </div>
      </div>
    </aside>

    <!-- Main Content Area -->
    <main class="flex-1 flex flex-col h-full overflow-hidden relative z-10">
      <!-- Drag Region Header -->
      <header data-tauri-drag-region class="h-16 flex items-center px-8 shrink-0">
        <div class="flex flex-col">
            <h2 class="text-sm font-medium text-white/90">
             {{ navItems.find(i => i.id === activeTab)?.label }}
            </h2>
            <span class="text-[11px] text-zinc-500">
                工作区 / {{ activeTab }}
            </span>
        </div>
      </header>

      <!-- Content Viewport -->
      <div class="flex-1 overflow-y-auto px-8 pb-8 scroll-smooth">
        <Transition 
          enter-active-class="transition duration-500 ease-[cubic-bezier(0.16,1,0.3,1)]" 
          enter-from-class="opacity-0 translate-y-4 scale-[0.98]" 
          enter-to-class="opacity-100 translate-y-0 scale-100"
          leave-active-class="transition duration-200 ease-in" 
          leave-from-class="opacity-100 scale-100" 
          leave-to-class="opacity-0 scale-[0.98]"
          mode="out-in"
        >
          <div :key="activeTab" class="h-full">
            <ImageCompressor v-if="activeTab === 'compressor'" />
            <Settings v-else-if="activeTab === 'settings'" />
            <div v-else class="h-full flex flex-col items-center justify-center text-zinc-600 space-y-4">
                 <div class="w-16 h-16 rounded-2xl border border-dashed border-zinc-700 flex items-center justify-center bg-zinc-900/50">
                     <Layers class="w-6 h-6 opacity-50" />
                 </div>
                 <p>该功能正在开发中...</p>
            </div>
          </div>
        </Transition>
      </div>
    </main>
  </div>
</template>
