<script lang="ts">
  import { untrack, createEventDispatcher } from 'svelte';
  import {
    type MonthlyBudgetGridResponse,
    type CategoryBudgetDetail,
    type CategoryGroupBudgetDetail,
    setBudget,
    applyRollingAverages,
    applyBulkBudget,
    deleteCategory,
    deleteCategoryGroup,
  } from '$lib/api';
  import { formatCents, centsToDollars, dollarsToCents } from '$lib/utils/currency';

  let {
    month = new Date().toISOString().slice(0, 7),
    grid = null,
    loading = false,
  }: {
    month?: string;
    grid?: MonthlyBudgetGridResponse | null;
    loading?: boolean;
  } = $props();

  const dispatch = createEventDispatcher<{
    monthChange: string;
    refresh: void;
    openSurplusModal: void;
    openCategoryModal: { defaultGroupId?: string };
  }>();

  let editingBudgeted: Record<string, string> = $state({});
  let applyingAverages = $state(false);

  // US-4.9 Bulk Budget Apply State
  let showBulkModal = $state(false);
  let bulkScope: 'year' | 'quarter' = $state('year');
  let bulkYear = $state(new Date().getFullYear());
  let bulkQuarter = $state(1);
  let bulkCategoryId = $state('');
  let bulkAmount = $state('');
  let bulkMode: 'divide' | 'repeat' = $state('repeat');
  let applyingBulk = $state(false);

  // Synchronize local input state with grid data when grid changes without infinite reactive loop
  $effect(() => {
    const currentGrid = grid;
    if (currentGrid && currentGrid.groups) {
      untrack(() => {
        const nextEdits: Record<string, string> = {};
        for (const group of currentGrid.groups) {
          for (const cat of group.categories) {
            nextEdits[cat.id] = (cat.budgeted_cents / 100).toFixed(2);
          }
        }
        editingBudgeted = nextEdits;
      });
    }
  });

  function navigateMonth(newMonth: string) {
    if (newMonth) {
      dispatch('monthChange', newMonth);
    }
  }

  function formatMonthTitle(monthStr: string): string {
    if (!monthStr || !monthStr.includes('-')) return monthStr;
    const [year, m] = monthStr.split('-');
    const date = new Date(parseInt(year), parseInt(m) - 1, 1);
    return date.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
  }

  async function handleBudgetBlur(cat: CategoryBudgetDetail) {
    const rawVal = editingBudgeted[cat.id];
    const newCents = dollarsToCents(rawVal);
    if (newCents !== cat.budgeted_cents) {
      try {
        await setBudget({
          month,
          category_id: cat.id,
          budgeted_cents: newCents,
        });
        dispatch('refresh');
      } catch (e: any) {
        alert(e.message || 'Failed to update budgeted amount.');
      }
    }
  }

  async function handleToggleCarryover(cat: CategoryBudgetDetail) {
    try {
      await setBudget({
        month,
        category_id: cat.id,
        carryover_enabled: !cat.carryover_enabled,
      });
      dispatch('refresh');
    } catch (e: any) {
      alert(e.message || 'Failed to update carryover setting.');
    }
  }

  async function handleApplySingle3MoAvg(cat: CategoryBudgetDetail) {
    try {
      await setBudget({
        month,
        category_id: cat.id,
        budgeted_cents: cat.rolling_3mo_avg_cents,
      });
      editingBudgeted[cat.id] = (cat.rolling_3mo_avg_cents / 100).toFixed(2);
      dispatch('refresh');
    } catch (e: any) {
      alert(e.message || 'Failed to apply 3-month average.');
    }
  }

  async function handleApplyAllRollingAverages() {
    if (confirm(`Apply 3-Month Rolling Averages to all categories for ${formatMonthTitle(month)}?`)) {
      applyingAverages = true;
      try {
        const res = await applyRollingAverages(month, 3);
        alert(`Successfully applied 3-month averages to ${res.updated_count} categories!`);
        dispatch('refresh');
      } catch (e: any) {
        alert(e.message || 'Failed to apply rolling averages.');
      } finally {
        applyingAverages = false;
      }
    }
  }

  async function handleApplyBulkSubmit(e: Event) {
    e.preventDefault();
    const cents = dollarsToCents(bulkAmount);
    if (cents <= 0) {
      alert('Please enter a valid amount greater than 0.');
      return;
    }
    applyingBulk = true;
    try {
      const res = await applyBulkBudget({
        category_id: bulkCategoryId || null,
        scope_type: bulkScope,
        year: bulkYear,
        quarter: bulkScope === 'quarter' ? bulkQuarter : undefined,
        amount_cents: cents,
        mode: bulkMode,
      });
      alert(`Successfully updated ${res.total_updates} monthly budget entries!`);
      showBulkModal = false;
      dispatch('refresh');
    } catch (e: any) {
      alert(e.message || 'Failed to bulk apply budget.');
    } finally {
      applyingBulk = false;
    }
  }

  async function handleDeleteCategory(categoryId: string, categoryName: string) {
    if (confirm(`Are you sure you want to remove/archive category "${categoryName}"?`)) {
      try {
        const res = await deleteCategory(categoryId);
        if (res.message) alert(res.message);
        dispatch('refresh');
      } catch (e: any) {
        alert(e.message || 'Failed to delete category.');
      }
    }
  }

  async function handleDeleteCategoryGroup(groupId: string, groupName: string) {
    if (confirm(`Are you sure you want to delete category group "${groupName}"?`)) {
      try {
        const res = await deleteCategoryGroup(groupId);
        if (res.message) alert(res.message);
        dispatch('refresh');
      } catch (e: any) {
        alert(e.message || 'Failed to delete category group.');
      }
    }
  }
</script>

<div class="space-y-6">
  <!-- Top Control Header: Month Navigator & Bulk Actions -->
  <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
    <!-- Month Navigation -->
    <div class="flex items-center gap-3">
      <button
        type="button"
        onclick={() => grid?.previous_month && navigateMonth(grid.previous_month)}
        disabled={!grid?.previous_month || loading}
        class="inline-flex items-center justify-center h-9 w-9 rounded-xl border border-slate-300 bg-white text-slate-700 shadow-xs hover:bg-slate-50 disabled:opacity-40 transition"
        title="Previous Month"
      >
        &larr;
      </button>

      <div class="flex items-center gap-2">
        <span class="text-lg font-black text-slate-900 min-w-[160px] text-center">
          {formatMonthTitle(month)}
        </span>
        <input
          type="month"
          value={month}
          onchange={(e) => navigateMonth(e.currentTarget.value)}
          class="rounded-xl border border-slate-300 px-2 py-1 text-xs font-semibold text-slate-700 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        />
      </div>

      <button
        type="button"
        onclick={() => grid?.next_month && navigateMonth(grid.next_month)}
        disabled={!grid?.next_month || loading}
        class="inline-flex items-center justify-center h-9 w-9 rounded-xl border border-slate-300 bg-white text-slate-700 shadow-xs hover:bg-slate-50 disabled:opacity-40 transition"
        title="Next Month"
      >
        &rarr;
      </button>
    </div>

    <!-- Quick Actions -->
    <div class="flex flex-wrap items-center gap-2.5">
      <button
        type="button"
        onclick={() => dispatch('openCategoryModal', {})}
        disabled={loading}
        class="inline-flex items-center gap-1.5 rounded-xl border border-slate-300 bg-white px-3.5 py-2 text-xs font-bold text-slate-700 shadow-xs hover:bg-slate-50 transition"
      >
        <span>➕ Add Category / Group</span>
      </button>

      <button
        type="button"
        onclick={() => (showBulkModal = true)}
        disabled={loading}
        class="inline-flex items-center gap-1.5 rounded-xl border border-indigo-300 bg-indigo-600 px-3.5 py-2 text-xs font-bold text-white shadow-xs hover:bg-indigo-700 transition"
        title="Apply a budget amount for a full Year or Quarter (US-4.9)"
      >
        <span>🗓️ Bulk Budget (Year/Quarter)</span>
      </button>

      <button
        type="button"
        onclick={handleApplyAllRollingAverages}
        disabled={applyingAverages || loading}
        class="inline-flex items-center gap-1.5 rounded-xl border border-indigo-200 bg-indigo-50 px-3.5 py-2 text-xs font-bold text-indigo-700 shadow-xs hover:bg-indigo-100 transition"
      >
        <span>📊 Apply 3-Mo Averages</span>
      </button>

      <button
        type="button"
        onclick={() => dispatch('openSurplusModal')}
        disabled={loading}
        class="inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 px-4 py-2 text-xs font-bold text-white shadow-md hover:bg-emerald-700 active:scale-95 transition"
      >
        <span>💸 Sweep Surplus to Savings</span>
      </button>
    </div>
  </div>

  <!-- Executive Summary Cards -->
  {#if grid}
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <div class="p-4 rounded-2xl bg-white border border-slate-200 shadow-xs">
        <span class="text-xs font-bold uppercase tracking-wider text-slate-500">Total Income</span>
        <div class="mt-1 text-xl font-black text-slate-900">
          {formatCents(grid.total_income_cents)}
        </div>
      </div>

      <div class="p-4 rounded-2xl bg-white border border-slate-200 shadow-xs">
        <span class="text-xs font-bold uppercase tracking-wider text-slate-500">Total Budgeted</span>
        <div class="mt-1 text-xl font-black text-indigo-600">
          {formatCents(grid.total_budgeted_cents)}
        </div>
      </div>

      <div class="p-4 rounded-2xl bg-white border border-slate-200 shadow-xs">
        <span class="text-xs font-bold uppercase tracking-wider text-slate-500">Total Actual Spent</span>
        <div class="mt-1 text-xl font-black text-slate-900">
          {formatCents(grid.total_actual_cents)}
        </div>
      </div>

      <div class={`p-4 rounded-2xl border shadow-xs ${
        grid.total_available_cents >= 0
          ? 'bg-emerald-50/60 border-emerald-200 text-emerald-950'
          : 'bg-rose-50/60 border-rose-200 text-rose-950'
      }`}>
        <span class="text-xs font-bold uppercase tracking-wider opacity-75">Net Available / Surplus</span>
        <div class={`mt-1 text-xl font-black ${
          grid.total_available_cents >= 0 ? 'text-emerald-700' : 'text-rose-700'
        }`}>
          {formatCents(grid.total_available_cents)}
        </div>
      </div>
    </div>
  {/if}

  <!-- Budget Grid Table -->
  <div class="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
    {#if loading}
      <div class="p-12 text-center text-slate-500 font-semibold text-sm">
        Loading budget data...
      </div>
    {:else if !grid || !grid.groups || grid.groups.length === 0}
      <div class="p-12 text-center text-slate-500 font-semibold text-sm">
        No category groups found. Please define categories first.
      </div>
    {:else}
      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs text-slate-700">
          <thead class="bg-slate-100/80 border-b border-slate-200 uppercase text-[10px] font-extrabold text-slate-500 tracking-wider">
            <tr>
              <th scope="col" class="py-3.5 px-4 min-w-[180px]">Category</th>
              <th scope="col" class="py-3.5 px-3 min-w-[130px]">Budgeted ($)</th>
              <th scope="col" class="py-3.5 px-3 text-right">Actual ($)</th>
              <th scope="col" class="py-3.5 px-3 text-right">Rollover ($)</th>
              <th scope="col" class="py-3.5 px-3 text-right">Available ($)</th>
              <th scope="col" class="py-3.5 px-3 text-center">Rollover?</th>
              <th scope="col" class="py-3.5 px-3 text-right">3-Mo Avg</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            {#each grid.groups as group}
              <!-- Group Header Row -->
              <tr class="bg-slate-50/80 font-bold border-t border-b border-slate-200/70 group/header">
                <td class="py-2.5 px-4 text-slate-900 font-black tracking-tight text-sm">
                  <div class="flex items-center justify-between">
                    <span>{group.name}</span>
                    <div class="opacity-0 group-hover/header:opacity-100 flex items-center gap-1.5 transition">
                      <button
                        type="button"
                        onclick={() => dispatch('openCategoryModal', { defaultGroupId: group.id })}
                        class="px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-50 text-indigo-700 hover:bg-indigo-100 transition"
                        title="Add Category to group"
                      >
                        + Category
                      </button>
                      <button
                        type="button"
                        onclick={() => handleDeleteCategoryGroup(group.id, group.name)}
                        class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-rose-50 text-rose-600 hover:bg-rose-100 transition"
                        title="Delete Category Group"
                      >
                        🗑️
                      </button>
                    </div>
                  </div>
                </td>
                <td class="py-2.5 px-3 text-indigo-700 font-extrabold">
                  {formatCents(group.total_budgeted_cents)}
                </td>
                <td class="py-2.5 px-3 text-right text-slate-800">
                  {formatCents(group.total_actual_cents)}
                </td>
                <td class="py-2.5 px-3 text-right text-slate-400">&mdash;</td>
                <td class={`py-2.5 px-3 text-right font-black ${
                  group.total_available_cents >= 0 ? 'text-emerald-700' : 'text-rose-700'
                }`}>
                  {formatCents(group.total_available_cents)}
                </td>
                <td class="py-2.5 px-3 text-center text-slate-400">&mdash;</td>
                <td class="py-2.5 px-3 text-right text-slate-400">&mdash;</td>
              </tr>

              <!-- Categories Rows -->
              {#each group.categories as cat}
                <tr class="hover:bg-slate-50/60 transition group/row">
                  <!-- Name -->
                  <td class="py-2.5 px-4 font-semibold text-slate-800">
                    <div class="flex items-center justify-between">
                      <div class="flex items-center gap-2">
                        <span>{cat.name}</span>
                        {#if cat.is_income}
                          <span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-emerald-100 text-emerald-800">
                            Income
                          </span>
                        {/if}
                      </div>
                      <button
                        type="button"
                        onclick={() => handleDeleteCategory(cat.id, cat.name)}
                        class="opacity-0 group-hover/row:opacity-100 px-1.5 py-0.5 rounded text-[10px] font-bold bg-rose-50 text-rose-600 hover:bg-rose-100 transition"
                        title="Delete / Archive Category"
                      >
                        🗑️
                      </button>
                    </div>
                  </td>

                  <!-- Budgeted Input -->
                  <td class="py-2.5 px-3">
                    <div class="relative flex items-center">
                      <span class="absolute left-2.5 text-slate-400 text-xs font-bold">$</span>
                      <input
                        type="number"
                        step="0.01"
                        min="0"
                        bind:value={editingBudgeted[cat.id]}
                        onblur={() => handleBudgetBlur(cat)}
                        onkeydown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
                        class="w-24 rounded-lg border border-slate-300 bg-white pl-6 pr-2 py-1 text-xs font-bold text-slate-900 shadow-xs focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                      />
                    </div>
                  </td>

                  <!-- Actual -->
                  <td class="py-2.5 px-3 text-right font-medium text-slate-700">
                    {formatCents(cat.actual_cents)}
                  </td>

                  <!-- Previous Rollover -->
                  <td class="py-2.5 px-3 text-right font-medium text-slate-500">
                    {formatCents(cat.previous_rollover_cents)}
                  </td>

                  <!-- Available / Rollover Balance -->
                  <td class={`py-2.5 px-3 text-right font-extrabold ${
                    cat.available_cents >= 0 ? 'text-emerald-600' : 'text-rose-600'
                  }`}>
                    {formatCents(cat.available_cents)}
                  </td>

                  <!-- Carryover Toggle Switch -->
                  <td class="py-2.5 px-3 text-center">
                    <button
                      type="button"
                      onclick={() => handleToggleCarryover(cat)}
                      class={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                        cat.carryover_enabled ? 'bg-emerald-600' : 'bg-slate-300'
                      }`}
                      title={cat.carryover_enabled ? 'Carryover Enabled' : 'Carryover Disabled'}
                    >
                      <span
                        class={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                          cat.carryover_enabled ? 'translate-x-4' : 'translate-x-0'
                        }`}
                      ></span>
                    </button>
                  </td>

                  <!-- 3-Month Average & Quick Apply -->
                  <td class="py-2.5 px-3 text-right">
                    <div class="flex items-center justify-end gap-1.5">
                      <span class="font-medium text-slate-600">{formatCents(cat.rolling_3mo_avg_cents)}</span>
                      <button
                        type="button"
                        onclick={() => handleApplySingle3MoAvg(cat)}
                        class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-600 hover:bg-indigo-100 hover:text-indigo-700 transition"
                        title="Copy 3-Mo Avg to Budgeted"
                      >
                        Copy
                      </button>
                    </div>
                  </td>
                </tr>
              {/each}
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </div>

  <!-- US-4.9 Bulk Budget Apply Modal (Year / Quarter) -->
  {#if showBulkModal}
    <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div class="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl space-y-4">
        <div class="flex items-center justify-between border-b pb-3 border-slate-200">
          <div>
            <h3 class="text-lg font-bold text-slate-900">Bulk Apply Budget (Year / Quarter)</h3>
            <p class="text-xs text-slate-500">Apply a budget value across a full Year or Quarter (US-4.9)</p>
          </div>
          <button
            type="button"
            onclick={() => (showBulkModal = false)}
            class="text-slate-400 hover:text-slate-600 text-2xl font-bold"
          >
            &times;
          </button>
        </div>

        <form onsubmit={handleApplyBulkSubmit} class="space-y-4">
          <!-- Scope Selector: Year vs Quarter -->
          <div>
            <label class="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">Time Scope</label>
            <div class="grid grid-cols-2 rounded-xl bg-slate-100 p-1 text-xs font-bold">
              <button
                type="button"
                onclick={() => (bulkScope = 'year')}
                class={`py-1.5 rounded-lg transition ${bulkScope === 'year' ? 'bg-white text-indigo-700 shadow-xs' : 'text-slate-600'}`}
              >
                Full Year (12 months)
              </button>
              <button
                type="button"
                onclick={() => (bulkScope = 'quarter')}
                class={`py-1.5 rounded-lg transition ${bulkScope === 'quarter' ? 'bg-white text-indigo-700 shadow-xs' : 'text-slate-600'}`}
              >
                Quarter (3 months)
              </button>
            </div>
          </div>

          <!-- Year & Quarter Pickers -->
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label for="bulk-year-input" class="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">Year</label>
              <input
                id="bulk-year-input"
                type="number"
                min="2000"
                max="2100"
                bind:value={bulkYear}
                required
                class="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-bold text-slate-800 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>

            {#if bulkScope === 'quarter'}
              <div>
                <label for="bulk-quarter-select" class="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">Quarter</label>
                <select
                  id="bulk-quarter-select"
                  bind:value={bulkQuarter}
                  class="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-bold text-slate-800 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                >
                  <option value={1}>Q1 (Jan - Mar)</option>
                  <option value={2}>Q2 (Apr - Jun)</option>
                  <option value={3}>Q3 (Jul - Sep)</option>
                  <option value={4}>Q4 (Oct - Dec)</option>
                </select>
              </div>
            {/if}
          </div>

          <!-- Category Selector -->
          <div>
            <label for="bulk-category-select" class="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">Target Category</label>
            <select
              id="bulk-category-select"
              bind:value={bulkCategoryId}
              class="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-bold text-slate-800 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              <option value="">All Categories</option>
              {#if grid}
                {#each grid.groups as group}
                  <optgroup label={group.name}>
                    {#each group.categories as cat}
                      <option value={cat.id}>{cat.name}</option>
                    {/each}
                  </optgroup>
                {/each}
              {/if}
            </select>
          </div>

          <!-- Amount Input -->
          <div>
            <label for="bulk-amount-input" class="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">Budget Amount ($)</label>
            <div class="relative flex items-center">
              <span class="absolute left-3 text-slate-400 font-bold">$</span>
              <input
                id="bulk-amount-input"
                type="number"
                step="0.01"
                min="0.01"
                placeholder="0.00"
                bind:value={bulkAmount}
                required
                class="w-full rounded-xl border border-slate-300 bg-white pl-7 pr-3 py-2 text-xs font-bold text-slate-900 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>
          </div>

          <!-- Mode Selector: Repeat vs Divide -->
          <div>
            <label class="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">Application Mode</label>
            <div class="space-y-2 text-xs font-semibold text-slate-700">
              <label class="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="bulkMode"
                  value="repeat"
                  bind:group={bulkMode}
                  class="text-indigo-600 focus:ring-indigo-500"
                />
                <span>Set amount each month (e.g., $500/month across all months)</span>
              </label>

              <label class="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="bulkMode"
                  value="divide"
                  bind:group={bulkMode}
                  class="text-indigo-600 focus:ring-indigo-500"
                />
                <span>Divide total amount evenly across months (e.g., $6,000 total = $500/mo)</span>
              </label>
            </div>
          </div>

          <!-- Modal Actions -->
          <div class="flex items-center justify-end gap-3 pt-3">
            <button
              type="button"
              onclick={() => (showBulkModal = false)}
              class="rounded-xl border border-slate-300 bg-white px-4 py-2 text-xs font-bold text-slate-700 hover:bg-slate-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={applyingBulk}
              class="rounded-xl bg-indigo-600 px-5 py-2 text-xs font-bold text-white shadow-md hover:bg-indigo-700 active:scale-95 disabled:opacity-50"
            >
              {applyingBulk ? 'Applying...' : 'Apply Budget Value'}
            </button>
          </div>
        </form>
      </div>
    </div>
  {/if}
</div>
