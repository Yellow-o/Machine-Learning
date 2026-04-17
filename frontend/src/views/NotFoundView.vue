<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<template>
  <main class="wrap panel fade-up">
    <el-result icon="warning" title="页面不存在" sub-title="请返回监控控制台继续操作">
      <template #extra>
        <el-space>
          <el-button type="primary" @click="router.push('/dashboard')">去看板</el-button>
          <el-button @click="router.push('/events')">去事件中心</el-button>
        </el-space>
      </template>
    </el-result>
  </main>
</template>

<style scoped>
.wrap {
  min-height: 72vh;
  display: grid;
  place-items: center;
  padding: 14px;
}
</style>
