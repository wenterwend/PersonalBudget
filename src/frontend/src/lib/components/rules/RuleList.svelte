<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { Rule } from '$lib/api';

  let {
    rules = [],
    loading = false,
  }: {
    rules?: Rule[];
    loading?: boolean;
  } = $props();

  const dispatch = createEventDispatcher<{
    createRule: void;
    editRule: Rule;
    deleteRule: Rule;
    toggleActive: Rule;
    applySingle: Rule;
    applyAll: void;
  }>();

  let searchQuery = $state('');
  let filterDirection: 'all' | 'income' | 'expense' = $state('all');
  let filterActive: 'all' | 'active' | 'inactive' = $state('all');

  let filteredRules = $derived(
    rules.filter((r) => {
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const matchesMain =
          r.match_value.toLowerCase().includes(q) ||
          (r.target_payee && r.target_payee.toLowerCase().includes(q)) ||
          (r.target_category_name && r.target_category_name.toLowerCase().includes(q)) ||
          (r.secondary_match_value && r.secondary_match_value.toLowerCase().includes(q));
        if (!matchesMain) return false;
      }

      if (filterDirection !== 'all') {
        if (filterDirection === 'income' && r.amount_condition !== 'income') return false;
        if (filterDirection === 'expense' && r.amount_condition !== 'expense') return false;
      }

      if (filterActive === 'active' && !r.is_active) return false;
      if (filterActive === 'inactive' && r.is_active) return false;

      return true;
    })
  );

  function handleCreateRule() {
    dispatch('createRule');
  }

  function handleEditRule(rule: Rule) {
    dispatch('editRule', rule);
  }

  function handleDeleteRule(rule: Rule) {
    dispatch('deleteRule', rule);
  }

  function handleToggleActive(rule: Rule) {
    dispatch('toggleActive', rule);
  }

  function handleApplySingle(rule: Rule) {
    dispatch('applySingle', rule);
  }

  function handleApplyAll() {
    dispatch('applyAll');
  }
</script>

<div class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden mb-8">
  <div class="p-4 bg-slate-50 border-b border-slate-200 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
    <div>
      <h2 class="text-lg font-bold text-slate-800">Payee & Categorization Rules</h2>
      <p class="text-xs text-slate-500">Deterministic rules execute in priority order e.g. CONTAINS "WALMART" &rarr; Groceries</p>
    </div>

    <div class="flex items-center gap-3">
      <button
        type="button"
        onclick={handleApplyAll}
        class="inline-flex items-center gap-1.5 rounded-lg border border-indigo-300 bg-indigo-50 px-3 py-1.5 text-xs font-bold text-indigo-700 hover:bg-indigo-100 transition"
      >
        <span>⚡ Apply All Rules Retroactively</span>
      </button>

      <button
        type="button"
        onclick={handleCreateRule}
        class="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-bold text-white shadow-sm hover:bg-indigo-700 transition"
      >
        <span class="text-base font-bold leading-none">+</span> Add Rule
      </button>
    </div>
  </div>

  <!-- Filter & Search Toolbar (US-3.5) -->
  <div class="p-3 bg-slate-100/60 border-b border-slate-200 flex flex-col sm:flex-row items-center justify-between gap-3">
    <div class="relative w-full sm:w-80">
      <span class="absolute left-2.5 top-2 text-slate-400 text-xs">🔍</span>
      <input
        type="text"
        bind:value={searchQuery}
        placeholder="Search rules by payee, category, pattern..."
        class="w-full pl-7 pr-3 py-1.5 text-xs font-medium rounded-lg border border-slate-300 bg-white text-slate-900 focus:outline-none focus:ring-1 focus:ring-indigo-500"
      />
    </div>

    <div class="flex items-center gap-3 w-full sm:w-auto">
      <div class="flex items-center gap-1 text-xs">
        <label for="filter-direction" class="font-bold text-slate-600">Type:</label>
        <select
          id="filter-direction"
          bind:value={filterDirection}
          class="rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs font-semibold text-slate-800 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        >
          <option value="all">All Types</option>
          <option value="income">Income Only (+$$$)</option>
          <option value="expense">Expense Only (-$$$)</option>
        </select>
      </div>

      <div class="flex items-center gap-1 text-xs">
        <label for="filter-active" class="font-bold text-slate-600">Status:</label>
        <select
          id="filter-active"
          bind:value={filterActive}
          class="rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs font-semibold text-slate-800 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        >
          <option value="all">All Statuses</option>
          <option value="active">Active Only</option>
          <option value="inactive">Inactive Only</option>
        </select>
      </div>

      {#if searchQuery || filterDirection !== 'all' || filterActive !== 'all'}
        <button
          type="button"
          onclick={() => { searchQuery = ''; filterDirection = 'all'; filterActive = 'all'; }}
          class="text-xs text-indigo-600 font-bold hover:underline"
        >
          Reset Filters
        </button>
      {/if}
    </div>
  </div>

  <div class="overflow-x-auto">
    <table class="w-full text-left text-xs border-collapse">
      <thead>
        <tr class="bg-slate-100/70 text-slate-600 font-semibold border-b border-slate-200">
          <th class="py-2.5 px-4 text-center">Priority</th>
          <th class="py-2.5 px-4">Match Condition</th>
          <th class="py-2.5 px-4">Cleaned Payee Target</th>
          <th class="py-2.5 px-4">Category Target</th>
          <th class="py-2.5 px-4 text-center">Active</th>
          <th class="py-2.5 px-4 text-right">Actions</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-slate-100 text-slate-800">
        {#if loading}
          <tr>
            <td colspan="6" class="py-6 text-center text-slate-400 font-medium">
              Loading rules...
            </td>
          </tr>
        {:else if filteredRules.length === 0}
          <tr>
            <td colspan="6" class="py-6 text-center text-slate-400 font-medium">
              {rules.length === 0 ? 'No automation rules defined. Click "+ Add Rule" to clean bank payee text automatically.' : 'No rules match the current search or filter criteria.'}
            </td>
          </tr>
        {:else}
          {#each filteredRules as rule (rule.id)}
            <tr class={`hover:bg-slate-50 transition ${!rule.is_active ? 'opacity-50 bg-slate-50/50' : ''}`}>
              <td class="py-3 px-4 text-center font-bold text-slate-500">
                #{rule.priority}
              </td>

              <td class="py-3 px-4 font-mono font-medium">
                <div>
                  <span class="text-slate-400">{rule.match_field}</span>
                  <span class="font-bold text-indigo-600 uppercase text-[10px] mx-1">[{rule.match_type}]</span>
                  <span class="bg-slate-100 px-1.5 py-0.5 rounded text-slate-900 border font-bold">"{rule.match_value}"</span>

                  {#if rule.amount_condition === 'income'}
                    <span class="ml-1.5 px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">
                      Income Only (+$$$)
                    </span>
                  {:else if rule.amount_condition === 'expense'}
                    <span class="ml-1.5 px-1.5 py-0.5 rounded text-[10px] font-bold bg-rose-100 text-rose-800 border border-rose-200">
                      Expense Only (-$$$)
                    </span>
                  {/if}
                </div>

                {#if rule.secondary_match_field && rule.secondary_match_value}
                  <div class="mt-1 text-[11px] text-slate-500 font-sans flex items-center gap-1">
                    <span class="font-bold text-indigo-600">AND</span>
                    <span class="text-slate-400">{rule.secondary_match_field}</span>
                    <span class="font-bold text-indigo-600 uppercase text-[9px]">[{rule.secondary_match_type}]</span>
                    <span class="bg-slate-100 px-1 py-0.2 rounded text-slate-800 border font-bold">"{rule.secondary_match_value}"</span>
                  </div>
                {/if}
              </td>

              <td class="py-3 px-4 font-semibold text-slate-900">
                {rule.target_payee || '—'}
              </td>

              <td class="py-3 px-4">
                {#if rule.target_category_name}
                  <span class="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-bold bg-indigo-50 text-indigo-700">
                    {rule.target_category_name}
                  </span>
                {:else}
                  <span class="text-slate-400 italic">—</span>
                {/if}
              </td>

              <td class="py-3 px-4 text-center">
                <input
                  type="checkbox"
                  checked={rule.is_active}
                  onchange={() => handleToggleActive(rule)}
                  class="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                />
              </td>

              <td class="py-3 px-4 text-right whitespace-nowrap space-x-2">
                <button
                  type="button"
                  title="Run rule against history"
                  onclick={() => handleApplySingle(rule)}
                  class="font-semibold text-indigo-600 hover:text-indigo-800 text-xs"
                >
                  Apply
                </button>
                <button
                  type="button"
                  onclick={() => handleEditRule(rule)}
                  class="font-semibold text-slate-600 hover:text-slate-800 text-xs"
                >
                  Edit
                </button>
                <button
                  type="button"
                  onclick={() => handleDeleteRule(rule)}
                  class="font-semibold text-rose-600 hover:text-rose-800 text-xs"
                >
                  Delete
                </button>
              </td>
            </tr>
          {/each}
        {/if}
      </tbody>
    </table>
  </div>
</div>
