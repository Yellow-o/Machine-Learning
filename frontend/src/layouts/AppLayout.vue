<script setup lang="ts">
import { Monitor, PieChart, User, Warning } from '@element-plus/icons-vue'
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const router = useRouter()
const route = useRoute()
const drawerVisible = ref(false)
const themeMode = ref<'dark' | 'light'>('dark')
const isDarkMode = computed(() => themeMode.value === 'dark')

const menus = computed(() => {
  const base = [{ path: '/events', label: '事件中心', desc: '筛选、复核、申诉', icon: Warning }]
  if (authStore.isAdmin) {
    return [
      { path: '/dashboard', label: '运营看板', desc: '风险指标与趋势', icon: PieChart },
      ...base,
      { path: '/admin/users', label: '账号管理', desc: '角色与状态维护', icon: User },
    ]
  }
  return base
})

const pageTitle = computed(() => {
  if (route.path.startsWith('/dashboard')) return '运营看板'
  if (route.path.startsWith('/events')) return '事件中心'
  if (route.path.startsWith('/admin/users')) return '账号管理'
  return '驾驶监测系统'
})
const roleLabel = computed(() => (authStore.isAdmin ? '管理员' : '驾驶员'))
const roleTagType = computed(() => (authStore.isAdmin ? 'danger' : 'info'))

function go(path: string) {
  if (path !== route.path) {
    router.push(path)
  }
  drawerVisible.value = false
}

function applyTheme(mode: 'dark' | 'light') {
  themeMode.value = mode
  document.documentElement.dataset.theme = mode
  localStorage.setItem('dms_theme', mode)
}

function toggleTheme(value: string | number | boolean) {
  applyTheme(value ? 'dark' : 'light')
}

onMounted(() => {
  const saved = localStorage.getItem('dms_theme')
  if (saved === 'light' || saved === 'dark') {
    applyTheme(saved)
    return
  }
  applyTheme('dark')
})

async function logout() {
  await authStore.logout()
  router.replace('/login')
}
</script>

<template>
  <el-container class="shell">
    <el-aside width="280px" class="aside desktop-only">
      <header class="brand">
        <el-icon><Monitor /></el-icon>
        <div>
          <h1>DMS 控制台</h1>
          <p>工业监控驾驶风险平台</p>
        </div>
      </header>

      <el-menu class="menu" :default-active="route.path" @select="go">
        <el-menu-item v-for="item in menus" :key="item.path" :index="item.path">
          <el-icon><component :is="item.icon" /></el-icon>
          <div class="menu-text">
            <span>{{ item.label }}</span>
            <small>{{ item.desc }}</small>
          </div>
        </el-menu-item>
      </el-menu>

      <footer class="aside-foot">
        <span>{{ authStore.user?.display_name || authStore.user?.username }}</span>
        <el-tag :type="authStore.isAdmin ? 'danger' : 'info'" round>{{ authStore.isAdmin ? '管理员' : '驾驶员' }}</el-tag>
      </footer>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="header-left">
          <el-button class="mobile-only" text @click="drawerVisible = true">菜单</el-button>
          <h2>{{ pageTitle }}</h2>
        </div>
        <div class="header-right">
          <el-switch
            :model-value="isDarkMode"
            inline-prompt
            active-text="夜"
            inactive-text="昼"
            @change="toggleTheme"
          />
          <el-tag :type="roleTagType" effect="light" round>{{ roleLabel }}</el-tag>
          <el-tag type="info" effect="dark">{{ authStore.user?.username }}</el-tag>
          <el-button type="danger" plain @click="logout">退出</el-button>
        </div>
      </el-header>

      <el-main class="content">
        <router-view />
      </el-main>
    </el-container>

    <el-drawer v-model="drawerVisible" title="导航菜单" direction="ltr" size="280px">
      <el-menu :default-active="route.path" @select="go">
        <el-menu-item v-for="item in menus" :key="item.path" :index="item.path">
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </el-menu-item>
      </el-menu>
    </el-drawer>
  </el-container>
</template>

<style scoped>
.shell {
  min-height: 100vh;
}

.aside {
  border-right: 1px solid var(--line-soft);
  background: linear-gradient(180deg, var(--aside-bg-start) 0%, var(--aside-bg-end) 100%);
  display: flex;
  flex-direction: column;
  padding: 16px 14px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border: 1px solid var(--line-soft);
  border-radius: 12px;
  background: var(--brand-card-bg);
}

.brand .el-icon {
  font-size: 22px;
  color: var(--brand-0);
}

.brand p {
  margin: 3px 0 0;
  color: var(--ink-2);
  font-size: 12px;
}

.menu {
  margin-top: 16px;
  border-right: 0;
  background: transparent;
}

.menu :deep(.el-menu-item) {
  height: auto;
  min-height: 68px;
  line-height: 1.2;
  padding: 10px 12px;
  display: flex;
  align-items: flex-start;
  gap: 8px;
  border-radius: 10px;
}

.menu :deep(.el-menu-item:hover) {
  background: var(--menu-hover-bg);
}

.menu :deep(.el-menu-item.is-active) {
  background: var(--menu-active-bg);
}

.menu :deep(.el-menu-item .el-icon) {
  margin-top: 4px;
  font-size: 18px;
}

.menu-text {
  display: grid;
  gap: 2px;
  margin-left: 4px;
  align-content: center;
  line-height: 1.25;
}

.menu-text span {
  color: var(--ink-0);
  font-size: 17px;
  font-weight: 700;
}

.menu-text small {
  color: var(--ink-2);
  font-size: 13px;
}

.aside-foot {
  margin-top: auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border: 1px solid var(--line-soft);
  border-radius: 10px;
  padding: 10px;
  color: var(--ink-1);
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--line-soft);
  background: var(--header-bg);
  backdrop-filter: blur(8px);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.content {
  padding: 16px;
}

.mobile-only {
  display: none;
}

@media (max-width: 960px) {
  .desktop-only {
    display: none;
  }

  .mobile-only {
    display: inline-flex;
  }

  .content {
    padding: 12px;
  }
}
</style>
