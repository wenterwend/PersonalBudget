<script lang="ts">
  import { untrack, createEventDispatcher } from 'svelte';
  import {
    type Account,
    type MonthlyBudgetGridResponse,
    type CategoryBudgetDetail,
    transferSurplusToSavings,
  } from '$lib/api';
  import { formatCents } from '$lib/utils/currency';

  let {
    show = false,
    month = '',
    grid = null,
    accounts = [],
  }: {
    show?: boolean;
    month?: string;
    grid?: MonthlyBudgetGridResponse | null;
    accounts?: Account[];
  } = $props();

  const dispatch = createEventDispatcher<{
    complete: { transferred_cents: number; target_account_name: string; transferred_categories: string[] };
    close: void;
  }>();

  let selectedCategoryIds: string[] = $state([]);
  let targetAccountId: string = $state('');
  let loading = $state(false);
  let error: string | null = $state(null);

  // Extract all categories with positive unspent surplus
  let surplusCategories: CategoryBudgetDetail[] = $derived.by(() => {
    if (!grid || !grid.groups) return [];
    const list: CategoryBudgetDetail[] = [];
    for (const group of grid.groups) {
      for (const cat of group.categories) {
        if (cat.available_cents > 0) {
          list.push(cat);
        }
      }
    }
    return list;
  });

  $effect(() => {
    if (show) {
      untrack(() => {
        // Pre-select all available surplus categories
        selectedCategoryIds = surplusCategories.map((c) => c.id);
        // Pre-select target account: prefer savings account, else first open account
        const openAccounts = accounts.filter((a) => !a.is_closed);
        const savingsAccount = openAccounts.find((a) => a.type === 'savings');
        if (savingsAccount) {
          targetAccountId = savingsAccount.id;
        } else if (openAccounts.length > 0) {
          targetAccountId = openAccounts[0].id;
        } else {
          targetAccountId = '';
        }
        error = null;
      });
    }
  });

  let totalSurplusCents = $derived(
    surplusCategories
      .filter((c) => selectedCategoryIds.includes(c.id))
      .reduce((sum, c) => sum + c.available_cents, 0)
  );

  function toggleCategory(catId: string) {
    if (selectedCategoryIds.includes(catId)) {
      selectedCategoryIds = selectedCategoryIds.filter((id) => id !== catId);
    } else {
      selectedCategoryIds = [...selectedCategoryIds, catId];
    }
  }

  function selectAll() {
    selectedCategoryIds = surplusCategories.map((c) => c.id);
  }

  function deselectAll() {
    selectedCategoryIds = [];
  }

  async function handleSubmit(e: Event) {
    e.preventDefault();
    if (!targetAccountId) {
      error = 'Please select a target account.';
      return;
    }
    if (selectedCategoryIds.length === 0) {
      error = 'Please select at least one category to transfer.';
      return;
    }

    loading = true;
    error = null;

    try {
      const result = await transferSurplusToSavings({
        month,
        category_ids: selectedCategoryIds,
        target_account_id: targetAccountId,
      });

      dispatch('complete', result);
      dispatch('close');
    } catch (err: any) {
      error = err.message || 'Failed to transfer category surplus.';
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
    <div class="w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl transition-all">
      <!-- Modal Header -->
      <div class="flex items-center justify-between pb-4 border-b border-slate-200">
        <div>
          <h2 class="text-xl font-bold text-slate-900">Transfer Surplus to Savings</h2>
          <p class="text-xs text-slate-500 mt-0.5">
            Sweep unspent category balances into a target account for {month}
          </p>
        </div>
        <button
          type="button"
          onclick={handleClose}
          class="text-slate-400 hover:text-slate-600 text-2xl font-bold"
        >
          &times;
        </button>
      </div>

      {#if error}
        <div class="mt-4 p-3 rounded-xl bg-red-50 text-red-700 text-xs font-semibold border border-red-200">
          {error}
        </div>
      {/if}

      <form onsubmit={handleSubmit} class="mt-4 space-y-4">
        <!-- Target Savings Account Selector -->
        <div>
          <label for="target-account-select" class="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
            Target Account
          </label>
          <select
            id="target-account-select"
            bind:value={targetAccountId}
            required
            class="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-800 shadow-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
          >
            <option value="" disabled>Select Target Account</option>
            {#each accounts.filter((a) => !a.is_closed) as account}
              <option value={account.id}>
                {account.name} ({account.type.toUpperCase()}) &bull; {formatCents(account.current_balance_cents, account.currency)}
              </option>
            {/each}
          </select>
        </div>

        <!-- Surplus Categories Selection -->
        <div>
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs font-bold uppercase tracking-wider text-slate-600">
              Select Categories with Surplus ({surplusCategories.length})
            </span>
            <div class="space-x-2 text-xs">
              <button type="button" onclick={selectAll} class="text-emerald-600 hover:underline font-semibold">Select All</button>
              <span class="text-slate-300">|</span>
              <button type="button" onclick={deselectAll} class="text-slate-500 hover:underline">Deselect All</button>
            </div>
          </div>

          {#if surplusCategories.length === 0}
            <div class="p-6 text-center rounded-xl bg-slate-50 border border-dashed border-slate-200 text-slate-500 text-sm">
              No categories have a positive unspent surplus for this month.
            </div>
          {:else}
            <div class="max-h-60 overflow-y-auto space-y-2 border rounded-xl border-slate-200 p-2 bg-slate-50/50">
              {#each surplusCategories as cat}
                <label
                  class={`flex items-center justify-between p-2.5 rounded-lg border text-xs font-medium cursor-pointer transition ${
                    selectedCategoryIds.includes(cat.id)
                      ? 'bg-emerald-50/70 border-emerald-300 text-emerald-950'
                      : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-50'
                  }`}
                >
                  <div class="flex items-center gap-3">
                    <input
                      type="checkbox"
                      checked={selectedCategoryIds.includes(cat.id)}
                      onchange={() => toggleCategory(cat.id)}
                      class="h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                    />
                    <span class="font-bold">{cat.name}</span>
                  </div>
                  <span class="font-bold text-emerald-600 bg-white px-2 py-0.5 rounded border border-emerald-200 shadow-xs">
                    +{formatCents(cat.available_cents)}
                  </span>
                </label>
              {/each}
            </div>
          {/if}
        </div>

        <!-- Total Summary Banner -->
        <div class="flex items-center justify-between p-3.5 rounded-xl bg-emerald-600 text-white shadow-md">
          <span class="text-xs font-bold uppercase tracking-wider">Total Surplus to Transfer</span>
          <span class="text-lg font-black">{formatCents(totalSurplusCents)}</span>
        </div>

        <!-- Form Buttons -->
        <div class="flex items-center justify-end gap-3 pt-2">
          <button
            type="button"
            onclick={handleClose}
            class="rounded-xl border border-slate-300 bg-white px-4 py-2 text-xs font-bold text-slate-700 shadow-sm hover:bg-slate-50 transition"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={loading || surplusCategories.length === 0 || selectedCategoryIds.length === 0}
            class="rounded-xl bg-emerald-600 px-5 py-2 text-xs font-bold text-white shadow-md hover:bg-emerald-700 active:scale-95 disabled:opacity-50 disabled:pointer-events-none transition"
          >
            {loading ? 'Transferring...' : 'Execute Surplus Transfer'}
          </button>
        </div>
      </form>
    </div>
  </div>
{/if}
