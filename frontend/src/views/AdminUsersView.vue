<script setup lang="ts">
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'

import { useAdminUsersStore } from '@/stores/adminUsers'
import type { AdminUser } from '@/types/api'

const usersStore = useAdminUsersStore()

const createVisible = ref(false)
const editVisible = ref(false)
const currentUser = ref<AdminUser | null>(null)

const createFormRef = ref<FormInstance>()
const editFormRef = ref<FormInstance>()

const createForm = reactive({
  username: '',
  password: '',
  full_name: '',
  role: 'driver' as 'admin' | 'driver',
  phone: '',
})

const editForm = reactive({
  full_name: '',
  role: 'driver' as 'admin' | 'driver',
  phone: '',
  is_active: true,
})

const createRules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

const roleOptions = [
  { label: '管理员', value: 'admin' },
  { label: '驾驶员', value: 'driver' },
]

const totalText = computed(() => `共 ${usersStore.pagination.total} 个账号`)

async function queryUsers(reset = false) {
  try {
    await usersStore.fetchList(reset)
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '加载失败')
  }
}

function resetFilters() {
  usersStore.resetFilters()
  queryUsers(true)
}

function openCreate() {
  createForm.username = ''
  createForm.password = ''
  createForm.full_name = ''
  createForm.role = 'driver'
  createForm.phone = ''
  createVisible.value = true
}

function openEdit(row: AdminUser) {
  currentUser.value = row
  editForm.full_name = row.full_name || row.display_name || ''
  editForm.role = row.role
  editForm.phone = row.phone || ''
  editForm.is_active = row.is_active
  editVisible.value = true
}

async function submitCreate() {
  if (!createFormRef.value) return
  const valid = await createFormRef.value.validate().catch(() => false)
  if (!valid) return

  try {
    await usersStore.createUser({
      username: createForm.username,
      password: createForm.password,
      full_name: createForm.full_name,
      role: createForm.role,
      phone: createForm.phone,
      is_active: true,
    })
    ElMessage.success('账号创建成功')
    createVisible.value = false
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '创建失败')
  }
}

async function submitEdit() {
  if (!currentUser.value || !editFormRef.value) return
  const valid = await editFormRef.value.validate().catch(() => false)
  if (!valid) return

  try {
    await usersStore.patchUser(currentUser.value.id, {
      full_name: editForm.full_name,
      role: editForm.role,
      phone: editForm.phone,
      is_active: editForm.is_active,
    })
    ElMessage.success('账号已更新')
    editVisible.value = false
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '更新失败')
  }
}

async function toggleActive(row: AdminUser, val: boolean) {
  try {
    await usersStore.patchUser(row.id, { is_active: val })
    ElMessage.success('账号状态已更新')
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '更新失败')
  }
}

async function onPageChange(page: number) {
  usersStore.pagination.page = page
  await queryUsers()
}

async function onPageSizeChange(size: number) {
  usersStore.pagination.page_size = size
  usersStore.pagination.page = 1
  await queryUsers()
}

onMounted(() => {
  queryUsers().catch(() => {})
})
</script>

<template>
  <section class="grid fade-up">
    <header class="page-head">
      <div>
        <h3>账号与角色管理</h3>
        <p>管理员可创建账号、调整角色并控制启停用状态</p>
      </div>
      <div class="head-actions">
        <span class="total">{{ totalText }}</span>
        <el-button type="primary" @click="openCreate">新建账号</el-button>
      </div>
    </header>

    <el-card class="panel" shadow="never">
      <div class="filters">
        <el-input v-model="usersStore.filters.q" clearable placeholder="用户名 / 姓名 / 手机" @keyup.enter="queryUsers(true)" />
        <el-select v-model="usersStore.filters.role" placeholder="角色" clearable>
          <el-option label="管理员" value="admin" />
          <el-option label="驾驶员" value="driver" />
        </el-select>
        <el-select v-model="usersStore.filters.is_active" placeholder="状态" clearable>
          <el-option label="启用" value="true" />
          <el-option label="停用" value="false" />
        </el-select>
        <div class="actions">
          <el-button type="primary" @click="queryUsers(true)">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </div>
      </div>
    </el-card>

    <el-alert v-if="usersStore.error" type="error" :title="usersStore.error" :closable="false" show-icon />

    <el-card class="panel" shadow="never">
      <el-table :data="usersStore.items" stripe v-loading="usersStore.loading">
        <el-table-column prop="id" label="ID" width="78" />
        <el-table-column prop="username" label="用户名" min-width="120" />
        <el-table-column prop="display_name" label="显示名" min-width="140" />
        <el-table-column prop="phone" label="手机号" min-width="140" />
        <el-table-column label="角色" width="120">
          <template #default="{ row }">
            <el-tag :type="row.role === 'admin' ? 'danger' : 'info'">{{ row.role === 'admin' ? '管理员' : '驾驶员' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-switch
              :model-value="row.is_active"
              active-text="启用"
              inactive-text="停用"
              @change="(v) => toggleActive(row, Boolean(v))"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager-wrap">
        <el-pagination
          layout="total, sizes, prev, pager, next"
          :total="usersStore.pagination.total"
          :page-size="usersStore.pagination.page_size"
          :current-page="usersStore.pagination.page"
          :page-sizes="[10, 20, 50, 100]"
          @current-change="onPageChange"
          @size-change="onPageSizeChange"
        />
      </div>
    </el-card>

    <el-dialog v-model="createVisible" title="新建账号" width="500px">
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-position="top">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="createForm.username" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="createForm.password" show-password type="password" />
        </el-form-item>
        <el-form-item label="显示名">
          <el-input v-model="createForm.full_name" />
        </el-form-item>
        <el-form-item label="手机号">
          <el-input v-model="createForm.phone" />
        </el-form-item>
        <el-form-item label="角色">
          <el-radio-group v-model="createForm.role">
            <el-radio-button v-for="item in roleOptions" :key="item.value" :value="item.value">
              {{ item.label }}
            </el-radio-button>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="usersStore.actionLoading" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editVisible" title="编辑账号" width="500px">
      <el-form ref="editFormRef" :model="editForm" label-position="top">
        <el-form-item label="显示名">
          <el-input v-model="editForm.full_name" />
        </el-form-item>
        <el-form-item label="手机号">
          <el-input v-model="editForm.phone" />
        </el-form-item>
        <el-form-item label="角色">
          <el-radio-group v-model="editForm.role">
            <el-radio-button v-for="item in roleOptions" :key="item.value" :value="item.value">
              {{ item.label }}
            </el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="账号状态">
          <el-switch v-model="editForm.is_active" active-text="启用" inactive-text="停用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="usersStore.actionLoading" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.head-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}

.total {
  color: var(--ink-2);
  font-size: 12px;
}

.filters {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.actions {
  display: flex;
  gap: 8px;
}

.pager-wrap {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 980px) {
  .filters {
    grid-template-columns: 1fr;
  }
}
</style>
