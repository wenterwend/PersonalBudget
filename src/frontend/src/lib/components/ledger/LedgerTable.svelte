<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { Transaction } from '$lib/api';
  import { formatCents } from '$lib/utils/currency';

  let {
    transactions = [],
    showAccountColumn = true,
    loading = false,
  }: {
    transactions?: Transaction[];
    showAccountColumn?: boolean;
    loading?: boolean;
  } = $props();

  const dispatch = createEventDispatcher<{
    edit: Transaction;
    delete: Transaction;
    confirmCategory: { transaction: Transaction; categoryId?: string; batch?: boolean };
    filterChange: { search: string; startDate: string; endDate: string; cleared: string };
  }>();

  let search = $state('');
  let startDate = $state('');
  let endDate = $state('');
  let clearedFilter = $state('');

  let expandedTxIds = $state(new Set<string>());

  function toggleExpand(id: string) {
    const next = new Set(expandedTxIds);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    expandedTxIds = next;
  }

  function handleFilter() {
    dispatch('filterChange', {
      search,
      startDate,
      endDate,
      cleared: clearedFilter,
    });
  }

  function handleConfirm(tx: Transaction, categoryId?: string, batch = false) {
    dispatch('confirmCategory', { transaction: tx, categoryId, batch });
  }

  let totalSumCents = $derived(transactions.reduce((sum, tx) => sum + tx.amount_cents, 0));
</script>

<div class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
  <!-- Filter Toolbar -->
  <div class="p-4 bg-slate-50 border-b border-slate-200 flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4">
    <div class="flex-1 flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
      <div class="relative flex-1">
        <input
          type="text"
          bind:value={search}
          oninput={handleFilter}
          placeholder="Search payee or notes..."
          class="w-full pl-9 pr-3 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        />
        <svg class="w-4 h-4 text-slate-400 absolute left-2.5 top-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
        </svg>
      </div>

      <div class="flex items-center gap-2">
        <input
          type="date"
          bind:value={startDate}
          onchange={handleFilter}
          class="py-1.5 px-2 text-xs rounded-lg border border-slate-300 focus:ring-indigo-500"
          title="Start Date"
        />
        <span class="text-xs text-slate-400">to</span>
        <input
          type="date"
          bind:value={endDate}
          onchange={handleFilter}
          class="py-1.5 px-2 text-xs rounded-lg border border-slate-300 focus:ring-indigo-500"
          title="End Date"
        />
      </div>

      <select
        bind:value={clearedFilter}
        onchange={handleFilter}
        class="py-1.5 px-2 text-xs rounded-lg border border-slate-300 focus:ring-indigo-500"
      >
        <option value="">All Statuses</option>
        <option value="true">Cleared</option>
        <option value="false">Uncleared</option>
      </select>
    </div>

    <!-- Summary Stats -->
    <div class="flex items-center justify-between md:justify-end gap-4 text-xs font-semibold">
      <span class="text-slate-500">{transactions.length} transactions</span>
      <div class="flex items-center gap-1.5">
        <span class="text-slate-500">Net Total:</span>
        <span class={`font-bold px-2 py-0.5 rounded-full ${
          totalSumCents >= 0 ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800'
        }`}>
          {formatCents(totalSumCents)}
        </span>
      </div>
    </div>
  </div>

  <!-- Transactions Table -->
  <div class="overflow-x-auto">
    <table class="w-full text-left text-xs border-collapse">
      <thead>
        <tr class="bg-slate-100/70 text-slate-600 font-semibold border-b border-slate-200">
          <th class="py-3 px-4">Date</th>
          {#if showAccountColumn}
            <th class="py-3 px-4">Account</th>
          {/if}
          <th class="py-3 px-4">Payee</th>
          <th class="py-3 px-4">Category</th>
          <th class="py-3 px-4 text-right">Amount</th>
          <th class="py-3 px-4 text-center">Cleared</th>
          <th class="py-3 px-4 text-right">Actions</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-slate-100 text-slate-800">
        {#if loading}
          <tr>
            <td colspan="7" class="py-8 text-center text-slate-400 font-medium">
              Loading ledger transactions...
            </td>
          </tr>
        {:else if transactions.length === 0}
          <tr>
            <td colspan="7" class="py-8 text-center text-slate-400 font-medium">
              No transactions found. Click "+ Add Transaction" to log an expense or income.
            </td>
          </tr>
        {:else}
          {#each transactions as tx (tx.id)}
            <tr class="hover:bg-slate-50/80 transition">
              <td class="py-3 px-4 font-medium whitespace-nowrap text-slate-600">
                {tx.date}
              </td>

              {#if showAccountColumn}
                <td class="py-3 px-4 whitespace-nowrap font-medium text-slate-700">
                  {tx.account_name || 'Account'}
                </td>
              {/if}

              <td class="py-3 px-4 font-semibold text-slate-900">
                <div>{tx.raw_payee}</div>
                {#if tx.notes}
                  <div class="text-[11px] text-slate-400 font-normal">{tx.notes}</div>
                {/if}
              </td>

              <!-- Category Cell with One-Click ML Confirmation (US-3.4) -->
              <td class="py-3 px-4">
                {#if tx.is_split}
                  <button
                    type="button"
                    onclick={() => toggleExpand(tx.id)}
                    class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-bold bg-indigo-50 text-indigo-700 hover:bg-indigo-100 transition"
                  >
                    <span>Split ({tx.splits.length} categories)</span>
                    <span class="text-[9px]">{expandedTxIds.has(tx.id) ? '▲' : '▼'}</span>
                  </button>
                {:else if tx.is_ml_suggested}
                  <!-- ML Suggested Category Badge + One-Click & Batch Confirm Buttons (US-3.4, US-3.8) -->
                  <div class="flex flex-wrap items-center gap-1.5">
                    <span
                      class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-purple-100 text-purple-800 border border-purple-200"
                      title={`Machine learning prediction confidence: ${Math.round((tx.ml_confidence || 0) * 100)}%`}
                    >
                      <span>🤖 {tx.splits[0]?.category_name || 'Suggested'}</span>
                      <span class="text-[10px] text-purple-600 font-semibold">({Math.round((tx.ml_confidence || 0) * 100)}%)</span>
                    </span>

                    <button
                      type="button"
                      onclick={() => handleConfirm(tx, undefined, false)}
                      title="Confirm ML Category Suggestion (US-3.4)"
                      class="inline-flex items-center gap-0.5 rounded px-2 py-0.5 text-[11px] font-bold bg-emerald-600 text-white hover:bg-emerald-700 transition shadow-sm"
                    >
                      Confirm ✓
                    </button>

                    <button
                      type="button"
                      onclick={() => handleConfirm(tx, undefined, true)}
                      title="Confirm category for ALL similar transactions with same payee (US-3.8)"
                      class="inline-flex items-center gap-0.5 rounded px-2 py-0.5 text-[11px] font-bold bg-purple-700 text-white hover:bg-purple-800 transition shadow-sm"
                    >
                      Batch All
                    </button>
                  </div>
                {:else}
                  <span class="font-medium text-slate-700">
                    {tx.splits[0]?.category_name || 'Uncategorized'}
                  </span>
                {/if}
              </td>

              <td class={`py-3 px-4 text-right font-bold whitespace-nowrap ${
                tx.amount_cents >= 0 ? 'text-emerald-600' : 'text-slate-900'
              }`}>
                {formatCents(tx.amount_cents)}
              </td>

              <td class="py-3 px-4 text-center">
                {#if tx.cleared}
                  <span class="inline-flex items-center justify-center w-5 h-5 rounded-full bg-emerald-100 text-emerald-600 font-bold text-xs" title="Cleared">
                    ✓
                  </span>
                {:else}
                  <span class="inline-flex items-center justify-center w-5 h-5 rounded-full bg-slate-100 text-slate-400 font-bold text-xs" title="Uncleared">
                    ○
                  </span>
                {/if}
              </td>

              <td class="py-3 px-4 text-right whitespace-nowrap space-x-2">
                <button
                  type="button"
                  onclick={() => dispatch('edit', tx)}
                  class="font-semibold text-indigo-600 hover:text-indigo-800"
                >
                  Edit
                </button>
                <button
                  type="button"
                  onclick={() => dispatch('delete', tx)}
                  class="font-semibold text-rose-600 hover:text-rose-800"
                >
                  Delete
                </button>
              </td>
            </tr>

            <!-- Expanded Split Rows Details -->
            {#if tx.is_split && expandedTxIds.has(tx.id)}
              <tr class="bg-indigo-50/40 border-t border-b border-indigo-100">
                <td colspan="7" class="py-2.5 px-6">
                  <div class="space-y-1 text-xs">
                    <div class="text-[11px] font-bold text-indigo-900 uppercase tracking-wider mb-1">
                      Split Breakdown:
                    </div>
                    {#each tx.splits as split, idx (split.id)}
                      <div class="flex items-center justify-between py-1 border-b border-indigo-100/60 last:border-0">
                        <div class="flex items-center gap-2">
                          <span class="text-indigo-400 font-mono">#{idx + 1}</span>
                          <span class="font-medium text-slate-800">{split.category_name || 'Uncategorized'}</span>
                          {#if split.notes}
                            <span class="text-slate-400 text-[11px]">({split.notes})</span>
                          {/if}
                        </div>
                        <span class={`font-bold ${split.amount_cents >= 0 ? 'text-emerald-600' : 'text-slate-800'}`}>
                          {formatCents(split.amount_cents)}
                        </span>
                      </div>
                    {/each}
                  </div>
                </td>
              </tr>
            {/if}
          {/each}
        {/if}
      </tbody>
    </table>
  </div>
</div>
