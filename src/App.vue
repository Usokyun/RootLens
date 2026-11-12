<script setup lang="ts">
import {
  IconCloud,
  IconBulb,
  IconDashboard,
  IconExperiment,
  IconInfoCircle,
  IconMenuFold,
  IconMenuUnfold,
  IconRelation,
  IconStorage,
} from "@arco-design/web-vue/es/icon";
import type { Component } from "vue";
import { Modal } from "@arco-design/web-vue";
import { computed, onMounted, onBeforeUnmount, reactive, ref } from "vue";
import { RouterView, useRoute, useRouter } from "vue-router";

import { useAppPreferences } from "@/services/app-preferences";
import {
  getLocalSessionMeta,
  getLocalSessionEventName,
} from "@/services/rootlens-data";
import { resetDemoWorkspace } from "@/services/demo-reset";

interface NavItem {
  name: "materials" | "evidence" | "graphs";
  label: string;
  icon: Component;
}

const navItems: NavItem[] = [
  {
    name: "evidence",
    label: "证据浏览",
    icon: IconDashboard,
  },
  {
    name: "graphs",
    label: "关联分析",
    icon: IconRelation,
  },
  {
    name: "materials",
    label: "知识维护",
    icon: IconExperiment,
  },
];

const router = useRouter();
const route = useRoute();
const collapsed = ref(window.innerWidth < 900);
const responsiveSider = () => {
  collapsed.value = window.innerWidth < 900;
};
onMounted(() => window.addEventListener("resize", responsiveSider));
onBeforeUnmount(() => window.removeEventListener("resize", responsiveSider));
const backendConfigModalVisible = ref(false);
const backendConfigForm = reactive({
  host: "127.0.0.1",
  port: "8000",
});
const { preferences, updatePreferences } = useAppPreferences();
const resetVisible = ref(false);
const sessionVersion = ref(0);
const sessionMeta = computed(() => {
  void sessionVersion.value;
  return getLocalSessionMeta();
});
const sessionChanged = () => {
  sessionVersion.value++;
};
onMounted(() =>
  window.addEventListener(getLocalSessionEventName(), sessionChanged),
);
onBeforeUnmount(() =>
  window.removeEventListener(getLocalSessionEventName(), sessionChanged),
);
function changeWorkspace(commit: () => void) {
  const event = new Event("rootlens:before-workspace-change", {
    cancelable: true,
  });
  if (window.dispatchEvent(event)) {
    commit();
    return;
  }
  Modal.confirm({
    title: "放弃未保存的草稿并切换？",
    content: "已保存版本不受影响，未预览的表单输入和未保存变更将被放弃。",
    okText: "放弃并切换",
    cancelText: "继续编辑",
    onOk: commit,
  });
}

const sourceModeOptions = [
  { value: "mock", label: "Demo", icon: IconStorage },
  { value: "backend", label: "Backend", icon: IconCloud },
] as const;

const activeMenuKey = computed(() => {
  const matched = navItems.find((item) => item.name === route.name);
  return matched?.name ?? "evidence";
});

const currentPageLabel = computed(() => {
  return typeof route.meta.label === "string"
    ? route.meta.label
    : "RootLens 工作台";
});

const currentContextLabel = computed(() => {
  if (sessionMeta.value?.source === "import") return "回放资产 · 不执行重算";
  return preferences.value.dataSourceMode === "mock"
    ? "演示快照 · 候选解释"
    : "后端分析 · 候选解释";
});

const apiBaseLabel = computed(() => {
  if (preferences.value.dataSourceMode === "mock") {
    return "内置资产";
  }

  return preferences.value.apiBaseUrl.replace(/^https?:\/\//, "");
});

const backendConfigPreview = computed(() => {
  const host = backendConfigForm.host.trim() || "127.0.0.1";
  const port = backendConfigForm.port.trim() || "8000";
  return `http://${host}:${port}`;
});

function parseApiBaseUrl(value: string) {
  try {
    const url = new URL(value);
    return {
      host: url.hostname || "127.0.0.1",
      port: url.port || "8000",
    };
  } catch {
    return {
      host: "127.0.0.1",
      port: "8000",
    };
  }
}

function handleNavigate(key: string | number) {
  const target = String(key) as NavItem["name"];
  void router.push({
    name: target,
  });
}

function handleSourceModeChange(mode: "mock" | "backend") {
  changeWorkspace(() => updatePreferences({ dataSourceMode: mode }));
}

function openBackendConfigModal() {
  const parsed = parseApiBaseUrl(preferences.value.apiBaseUrl);
  backendConfigForm.host = parsed.host;
  backendConfigForm.port = parsed.port;
  backendConfigModalVisible.value = true;
}

function handleBackendConfigReset() {
  backendConfigForm.host = "127.0.0.1";
  backendConfigForm.port = "8000";
}

function handleBackendConfigSave() {
  const host = backendConfigForm.host.trim() || "127.0.0.1";
  const parsedPort = Number.parseInt(backendConfigForm.port.trim(), 10);
  const port =
    Number.isFinite(parsedPort) && parsedPort > 0 ? String(parsedPort) : "8000";

  changeWorkspace(() => {
    updatePreferences({ apiBaseUrl: `http://${host}:${port}` });
    backendConfigModalVisible.value = false;
  });
}
</script>

<template>
  <a-config-provider size="medium">
    <div class="app-shell">
      <header class="ocean-header">
        <div class="ocean-header__left">
          <div class="ocean-header__logo">
            <span class="ocean-header__logo-mark">RL</span>
            <span class="ocean-header__logo-text">RootLens</span>
          </div>
          <div class="ocean-header__divider" />
          <h1 class="ocean-header__title">
            <icon-dashboard />
            <span>{{ currentPageLabel }}</span>
          </h1>
        </div>
        <div class="ocean-header__right">
          <a-radio-group
            :model-value="preferences.dataSourceMode"
            type="button"
            aria-label="数据源模式"
            @change="handleSourceModeChange"
          >
            <a-radio
              v-for="item in sourceModeOptions"
              :key="item.value"
              :value="item.value"
            >
              <component :is="item.icon" />
              {{ item.label }}
            </a-radio>
          </a-radio-group>

          <a-button
            v-if="preferences.dataSourceMode === 'backend'"
            type="text"
            class="ocean-header__api-base-trigger"
            aria-label="修改后端地址"
            @click="openBackendConfigModal"
          >
            <template #icon><icon-cloud /></template>
            {{ apiBaseLabel }}
          </a-button>
          <a-tag v-else size="small" color="green">
            <icon-bulb />
            <span>{{ apiBaseLabel }}</span>
          </a-tag>
        </div>
        <a-button
          v-if="
            preferences.dataSourceMode === 'mock' &&
            sessionMeta?.source !== 'import'
          "
          type="text"
          @click="resetVisible = true"
          >重置演示</a-button
        >
        <a-tooltip :content="currentContextLabel">
          <div class="ocean-header__profile" aria-label="当前上下文">
            {{ currentContextLabel }}
          </div>
        </a-tooltip>
      </header>

      <a-layout class="ads-brain-workbench-layout" has-sider>
        <a-layout-sider
          class="app-sider-menu"
          :width="168"
          :collapsed-width="56"
          :collapsed="collapsed"
          hide-trigger
          breakpoint="xl"
        >
          <a-menu
            class="app-sider-menu__menu"
            :selected-keys="[activeMenuKey]"
            :collapse="collapsed"
            @menu-item-click="handleNavigate"
          >
            <a-menu-item v-for="item in navItems" :key="item.name">
              <template #icon>
                <component :is="item.icon" />
              </template>
              {{ item.label }}
            </a-menu-item>
          </a-menu>

          <a-button
            type="text"
            shape="square"
            class="app-sider-menu__collapse-btn"
            :aria-label="collapsed ? '展开侧边栏' : '收起侧边栏'"
            @click="collapsed = !collapsed"
          >
            <IconMenuUnfold v-if="collapsed" />
            <IconMenuFold v-else />
          </a-button>
        </a-layout-sider>

        <a-layout-content class="ads-brain-workbench-layout__content">
          <RouterView />
        </a-layout-content>
      </a-layout>

      <a-modal
        v-model:visible="resetVisible"
        title="重置演示工作区"
        @ok="resetDemoWorkspace"
      >
        仅清除本浏览器的 Demo
        反馈、知识草稿与当前选择。保留导入回放资产，不影响后端数据库。
      </a-modal>
      <a-modal
        v-model:visible="backendConfigModalVisible"
        title="修改后端地址"
        width="420px"
        @ok="handleBackendConfigSave"
      >
        <a-form
          id="app-form-1"
          :model="backendConfigForm"
          layout="vertical"
          class="ocean-header__modal-stack workspace-form"
        >
          <a-form-item
            field="host"
            label="域名 / IP"
            :label-attrs="{ for: 'backend-backendConfigForm-host-input' }"
            class="workspace-form-item"
          >
            <a-input
              :input-attrs="{
                id: 'backend-backendConfigForm-host-input',
                'aria-label': '域名 / IP',
              }"
              id="backend-backendConfigForm-host"
              aria-label="域名 / IP"
              v-model="backendConfigForm.host"
              placeholder="127.0.0.1"
            />
          </a-form-item>
          <a-form-item
            field="port"
            label="端口"
            :label-attrs="{ for: 'backend-backendConfigForm-port-input' }"
            class="workspace-form-item"
          >
            <a-input
              :input-attrs="{
                id: 'backend-backendConfigForm-port-input',
                'aria-label': '端口',
              }"
              id="backend-backendConfigForm-port"
              aria-label="端口"
              v-model="backendConfigForm.port"
              placeholder="8000"
            />
          </a-form-item>
          <div class="workspace-claim-note workspace-claim-note--compact">
            <span class="workspace-summary-label">
              <icon-info-circle />
              <span>预览</span>
            </span>
            <strong>{{ backendConfigPreview }}</strong>
          </div>
          <div class="rl-form-actions rl-form-actions--dual">
            <a-button size="small" @click="handleBackendConfigReset">
              恢复默认 127.0.0.1:8000
            </a-button>
          </div>
        </a-form>
      </a-modal>
    </div>
  </a-config-provider>
</template>
