<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import {
    type CategoryGroup,
    createCategory,
    createCategoryGroup,
  } from '$lib/api';

  let {
    show = false,
    categoryGroups = [],
    defaultGroupId = '',
  }: {
    show?: boolean;
    categoryGroups?: CategoryGroup[];
    defaultGroupId?: string;
  } = $props();

  const dispatch = createEventDispatcher<{ save: void; close: void }>();

  let mode: 'category' | 'group' = $state('category');
  let categoryName = $state('');
  let selectedGroupId = $state('');
  let isIncome = $state(false);

  let groupName = $state('');
  let loading = $state(false);
  let error: string | null = $state(null);

  $effect(() => {
    if (show) {
      mode = 'category';
      categoryName = '';
      groupName = '';
      isIncome = false;
      error = null;
      if (defaultGroupId) {
        selectedGroupId = defaultGroupId;
      } else if (categoryGroups.length > 0) {
        selectedGroupId = categoryGroups[0].id;
      } else {
        selectedGroupId = '';
      }
    }
  });

  async function handleSubmit(e: Event) {
    e.preventDefault();
    loading = true;
    error = null;

    try {
      if (mode === 'category') {
        if (!categoryName.trim()) {
          error = 'Category name is required.';
          loading = false;
          return;
        }
        if (!selectedGroupId) {
          error = 'Please select a category group.';
          loading = false;
          return;
        }
        await createCategory(selectedGroupId, categoryName.trim(), isIncome);
      } else {
        if (!groupName.trim()) {
          error = 'Category group name is required.';
          loading = false;
          return;
        }
        await createCategoryGroup(groupName.trim(), categoryGroups.length);
      }

      dispatch('save');
      dispatch('close');
    } catch (err: any) {
      error = err.message || 'Failed to save category.';
    } finally {
      loading = false;
    }
  }

  function handleClose() {
    dispatch('close');
  }
</script>

{#if show}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
    <div class="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl transition-all">
      <!-- Modal Header -->
      <div class="flex items-center justify-between pb-3 border-b border-slate-200">
        <h2 class="text-xl font-bold text-slate-900">Customize Budget Structure</h2>
        <button
          type="button"
          onclick={handleClose}
          class="text-slate-400 hover:text-slate-600 text-2xl font-bold"
        >
          &times;
        </button>
      </div>

      <!-- Mode Selector Tabs -->
      <div class="mt-4 grid grid-cols-2 rounded-xl bg-slate-100 p-1 text-xs font-bold">
        <button
          type="button"
          onclick={() => (mode = 'category')}
          class={`py-1.5 rounded-lg transition ${
            mode === 'category' ? 'bg-white text-indigo-700 shadow-xs' : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          + Add Category
        </button>
        <button
          type="button"
          onclick={() => (mode = 'group')}
          class={`py-1.5 rounded-lg transition ${
            mode === 'group' ? 'bg-white text-indigo-700 shadow-xs' : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          + Add Category Group
        </button>
      </div>

      {#if error}
        <div class="mt-4 p-3 rounded-xl bg-red-50 text-red-700 text-xs font-semibold border border-red-200">
          {error}
        </div>
      {/if}

      <form onsubmit={handleSubmit} class="mt-4 space-y-4">
        {#if mode === 'category'}
          <!-- Category Group Selector -->
          <div>
            <label for="category-group-select" class="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
              Parent Category Group
            </label>
            <select
              id="category-group-select"
              bind:value={selectedGroupId}
              required
              class="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-bold text-slate-800 shadow-xs focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              <option value="" disabled>Select Group</option>
              {#each categoryGroups as group}
                <option value={group.id}>{group.name}</option>
              {/each}
            </select>
          </div>

          <!-- Category Name -->
          <div>
            <label for="category-name-input" class="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
              Category Name
            </label>
            <input
              id="category-name-input"
              type="text"
              placeholder="e.g. Dining Out, Gym Membership"
              bind:value={categoryName}
              required
              class="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-bold text-slate-800 shadow-xs focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          <!-- Income vs Expense Toggle -->
          <label class="flex items-center gap-2 cursor-pointer pt-1">
            <input
              type="checkbox"
              bind:checked={isIncome}
              class="h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
            />
            <span class="text-xs font-bold text-slate-700">Income Category (e.g. Salary, Side Hustle)</span>
          </label>
        {:else}
          <!-- Group Name -->
          <div>
            <label for="group-name-input" class="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
              Category Group Name
            </label>
            <input
              id="group-name-input"
              type="text"
              placeholder="e.g. Subscriptions, Travel & Vacation"
              bind:value={groupName}
              required
              class="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-bold text-slate-800 shadow-xs focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>
        {/if}

        <!-- Form Action Buttons -->
        <div class="flex items-center justify-end gap-3 pt-3">
          <button
            type="button"
            onclick={handleClose}
            class="rounded-xl border border-slate-300 bg-white px-4 py-2 text-xs font-bold text-slate-700 shadow-xs hover:bg-slate-50 transition"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={loading}
            class="rounded-xl bg-indigo-600 px-5 py-2 text-xs font-bold text-white shadow-md hover:bg-indigo-700 active:scale-95 disabled:opacity-50 transition"
          >
            {loading ? 'Saving...' : mode === 'category' ? 'Create Category' : 'Create Group'}
          </button>
        </div>
      </form>
    </div>
  </div>
{/if}
