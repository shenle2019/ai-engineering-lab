<template>
  <v-card
    v-if="isOwnGroup"
    class="mt-4 d-print-none"
    variant="tonal"
    color="primary"
  >
    <v-card-title class="d-flex align-center flex-wrap ga-2">
      <v-icon start>
        {{ $globals.icons.robot }}
      </v-icon>
      <span>{{ $t("recipe.ai-summary.title") }}</span>
      <v-spacer />
      <v-btn
        v-if="summary"
        size="small"
        variant="text"
        :loading="loading"
        @click="generate"
      >
        {{ $t("recipe.ai-summary.regenerate") }}
      </v-btn>
      <v-btn
        v-else
        size="small"
        color="primary"
        :loading="loading"
        @click="generate"
      >
        {{ $t("recipe.ai-summary.generate") }}
      </v-btn>
    </v-card-title>

    <v-card-text>
      <div v-if="error" class="text-error">
        {{ $t("recipe.ai-summary.failed") }}
      </div>
      <p v-else-if="!summary" class="text-medium-emphasis mb-0">
        {{ $t("recipe.ai-summary.description") }}
      </p>
      <template v-else>
        <p class="text-body-1">
          {{ summary.summary }}
        </p>
        <div class="d-flex flex-wrap ga-2 mb-3">
          <v-chip size="small" color="primary" variant="flat">
            {{ $t("recipe.ai-summary.difficulty") }}: {{ difficultyLabel }}
          </v-chip>
          <v-chip size="small" variant="outlined">
            {{ $t("recipe.ai-summary.estimated-time") }}: {{ summary.estimated_time }}
          </v-chip>
        </div>
        <template v-if="summary.highlights?.length">
          <div class="text-subtitle-2 mb-1">
            {{ $t("recipe.ai-summary.highlights") }}
          </div>
          <ul class="mb-3">
            <li v-for="(item, index) in summary.highlights" :key="`highlight-${index}`">
              {{ item }}
            </li>
          </ul>
        </template>
        <v-alert v-if="summary.warnings?.length" type="warning" variant="tonal" density="compact">
          <div class="text-subtitle-2 mb-1">
            {{ $t("recipe.ai-summary.warnings") }}
          </div>
          <ul>
            <li v-for="(item, index) in summary.warnings" :key="`warning-${index}`">
              {{ item }}
            </li>
          </ul>
        </v-alert>
      </template>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import type { OpenAIRecipeSummary } from "~/lib/api/types/openai";
import { useUserApi } from "~/composables/api";
import { useLoggedInState } from "~/composables/use-logged-in-state";

const props = defineProps<{
  slug: string;
}>();

const { t } = useI18n();
const { isOwnGroup } = useLoggedInState();
const api = useUserApi();

const summary = ref<OpenAIRecipeSummary | null>(null);
const loading = ref(false);
const error = ref(false);

const difficultyLabel = computed(() => {
  const value = summary.value?.difficulty;
  if (!value) {
    return "";
  }

  return t(`recipe.ai-summary.difficulty-${value}`);
});

async function generate() {
  loading.value = true;
  error.value = false;

  const { data, error: apiError } = await api.recipes.generateAiSummary(props.slug);

  if (apiError || !data) {
    summary.value = null;
    error.value = true;
  }
  else {
    summary.value = data;
  }

  loading.value = false;
}
</script>
