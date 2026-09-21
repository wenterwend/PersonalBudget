<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { Rule, RuleCreate, CategoryGroup } from '$lib/api';
  import { createRule, updateRule, previewRule } from '$lib/api';

  let {
    show = false,
    ruleToEdit = null,
    categoryGroups = [],
  }: {
    show?: boolean;
    ruleToEdit?: Rule | null;
    categoryGroups?: CategoryGroup[];
  } = $props();

  const dispatch = createEventDispatcher<{ save: Rule; close: void }>();

  let priority = $state(1);
  let matchField: 'raw_payee' | 'notes' | 'amount' = $state('raw_payee');
  let matchType: 'contains' | 'exact' | 'starts_with' = $state('contains');
  let matchValue = $state('');
  let amountCondition: 'any' | 'income' | 'expense' = $state('any');
  let enableSecondary = $state(false);
  let secondaryMatchField: 'raw_payee' | 'notes' | 'amount' = $state('notes');
  let secondaryMatchType: 'contains' | 'exact' | 'starts_with' = $state('contains');
  let secondaryMatchValue = $state('');

  let targetPayee = $state('');
  let targetCategoryId = $state('');
  let isActive = $state(true);
  let applyRetroactive = $state(true);

  let error: string | null = $state(null);
  let loading = $state(false);

  let previewMatchCount: number | null = $state(null);
  let previewSamples: any[] = $state([]);
  let previewLoading = $state(false);

  $effect(() => {
    if (show && matchValue.trim().length >= 2) {
      fetchPreview();
    } else {
      previewMatchCount = null;
      previewSamples = [];
    }
  });

  async function fetchPreview() {
    if (!matchValue.trim()) return;
    previewLoading = true;
    try {
      const res = await previewRule({
        priority,
        match_field: matchField,
        match_type: matchType,
        match_value: matchValue.trim(),
        amount_condition: amountCondition,
        secondary_match_field: enableSecondary && secondaryMatchValue.trim() ? secondaryMatchField : null,
        secondary_match_type: enableSecondary && secondaryMatchValue.trim() ? secondaryMatchType : null,
        secondary_match_value: enableSecondary && secondaryMatchValue.trim() ? secondaryMatchValue.trim() : null,
        target_payee: targetPayee.trim() || undefined,
        target_category_id: targetCategoryId || undefined,
        is_active: true
      });
      previewMatchCount = res.match_count;
      previewSamples = res.sample_matches;
    } catch {
      previewMatchCount = null;
      previewSamples = [];
    } finally {
      previewLoading = false;
    }
  }

  $effect(() => {
    if (show) {
      if (ruleToEdit) {
        priority = ruleToEdit.priority;
        matchField = ruleToEdit.match_field;
        matchType = ruleToEdit.match_type;
        matchValue = ruleToEdit.match_value;
        amountCondition = ruleToEdit.amount_condition || 'any';
        if (ruleToEdit.secondary_match_field && ruleToEdit.secondary_match_value) {
          enableSecondary = true;
          secondaryMatchField = ruleToEdit.secondary_match_field;
          secondaryMatchType = ruleToEdit.secondary_match_type || 'contains';
          secondaryMatchValue = ruleToEdit.secondary_match_value;
        } else {
          enableSecondary = false;
          secondaryMatchField = 'notes';
          secondaryMatchType = 'contains';
          secondaryMatchValue = '';
        }
        targetPayee = ruleToEdit.target_payee || '';
        targetCategoryId = ruleToEdit.target_category_id || '';
        isActive = ruleToEdit.is_active;
        applyRetroactive = false;
      } else {
        priority = 1;
        matchField = 'raw_payee';
        matchType = 'contains';
        matchValue = '';
        amountCondition = 'any';
        enableSecondary = false;
        secondaryMatchField = 'notes';
        secondaryMatchType = 'contains';
        secondaryMatchValue = '';
        targetPayee = '';
        targetCategoryId = '';
        isActive = true;
        applyRetroactive = true;
      }
      error = null;
    }
  });

  async function handleSubmit() {
    if (!matchValue.trim()) {
      error = 'Match value text is required.';
      return;
    }
    if (!targetPayee.trim() && !targetCategoryId) {
      error = 'Please provide either a Target Standardized Payee or a Target Category.';
      return;
    }

    loading = true;
    error = null;

    try {
      const payload: RuleCreate = {
        priority,
        match_field: matchField,
        match_type: matchType,
        match_value: matchValue.trim(),
        amount_condition: amountCondition,
        secondary_match_field: enableSecondary && secondaryMatchValue.trim() ? secondaryMatchField : null,
        secondary_match_type: enableSecondary && secondaryMatchValue.trim() ? secondaryMatchType : null,
        secondary_match_value: enableSecondary && secondaryMatchValue.trim() ? secondaryMatchValue.trim() : null,
        target_payee: targetPayee.trim() || undefined,
        target_category_id: targetCategoryId || undefined,
        is_active: isActive,
      };

      let savedRule: Rule;
      if (ruleToEdit) {
        savedRule = await updateRule(ruleToEdit.id, payload, applyRetroactive);
      } else {
        savedRule = await createRule(payload, applyRetroactive);
      }

      dispatch('save', savedRule);
      dispatch('close');
    } catch (e: any) {
      error = e.message || 'Failed to save rule.';
    } finally {
      loading = false;
    }
  }

  function handleClose() {
    dispatch('close');
  }
</script>

{#if show}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 overflow-y-auto">
    <div class="w-full max-w-lg rounded-xl bg-white p-6 shadow-2xl my-8">
      <div class="flex items-center justify-between pb-3 border-b">
        <h2 class="text-xl font-bold text-slate-800">
          {ruleToEdit ? 'Edit Deterministic Rule' : 'Create New Automation Rule'}
        </h2>
        <button
          type="button"
          onclick={handleClose}
          class="text-slate-400 hover:text-slate-600 text-2xl font-semibold"
        >&times;</button>
      </div>

      {#if error}
        <div class="mt-4 p-3 rounded-lg bg-rose-50 text-rose-700 text-sm font-medium border border-rose-200">
          {error}
        </div>
      {/if}

      <form onsubmit={(e) => { e.preventDefault(); handleSubmit(); }} class="mt-4 space-y-4">
        <!-- Matching Criteria -->
        <div class="space-y-3 p-3 rounded-lg bg-slate-50 border border-slate-200">
          <h3 class="text-xs font-bold text-slate-700 uppercase">1. When Transaction Field Matches:</h3>
          
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label for="match-field-select" class="block text-xs font-medium text-slate-600">Match Field</label>
              <select
                id="match-field-select"
                bind:value={matchField}
                class="mt-1 block w-full rounded border border-slate-300 px-2.5 py-1.5 text-xs text-slate-900"
              >
                <option value="raw_payee">Raw Payee String</option>
                <option value="notes">Notes / Memo</option>
                <option value="amount">Amount (Cents)</option>
              </select>
            </div>

            <div>
              <label for="match-type-select" class="block text-xs font-medium text-slate-600">Match Condition</label>
              <select
                id="match-type-select"
                bind:value={matchType}
                class="mt-1 block w-full rounded border border-slate-300 px-2.5 py-1.5 text-xs text-slate-900"
              >
                <option value="contains">Contains (Case Insensitive)</option>
                <option value="exact">Exact Match</option>
                <option value="starts_with">Starts With</option>
              </select>
            </div>
          </div>

          <div>
            <label for="match-val-input" class="block text-xs font-medium text-slate-600">Search Pattern / Value *</label>
            <input
              id="match-val-input"
              type="text"
              bind:value={matchValue}
              placeholder="e.g. WALMART or STARBUCKS"
              required
              class="mt-1 block w-full rounded border border-slate-300 px-2.5 py-1.5 text-xs text-slate-900 focus:ring-indigo-500"
            />
          </div>

          <!-- Amount Direction Filter -->
          <div>
            <label for="amount-condition-select" class="block text-xs font-medium text-slate-600">Transaction Type / Direction Filter</label>
            <select
              id="amount-condition-select"
              bind:value={amountCondition}
              class="mt-1 block w-full rounded border border-slate-300 px-2.5 py-1.5 text-xs text-slate-900 font-semibold"
            >
              <option value="any">Any Amount (Income or Expense)</option>
              <option value="income">Income Only (+ Positive Amounts, e.g. Paychecks)</option>
              <option value="expense">Expense Only (- Negative Amounts, e.g. Purchases)</option>
            </select>
          </div>

          <!-- Secondary Condition Toggle -->
          <div class="pt-2 border-t border-slate-200">
            <label class="flex items-center gap-2 cursor-pointer text-xs font-semibold text-slate-700">
              <input
                type="checkbox"
                bind:checked={enableSecondary}
                class="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
              />
              <span>Add Secondary Condition (e.g. filter by Notes or Payee)</span>
            </label>

            {#if enableSecondary}
              <div class="mt-3 grid grid-cols-2 gap-3 pl-4 border-l-2 border-indigo-200">
                <div>
                  <label for="sec-match-field" class="block text-[11px] font-medium text-slate-600">2nd Field</label>
                  <select
                    id="sec-match-field"
                    bind:value={secondaryMatchField}
                    class="mt-1 block w-full rounded border border-slate-300 px-2 py-1 text-xs text-slate-900"
                  >
                    <option value="raw_payee">Raw Payee String</option>
                    <option value="notes">Notes / Memo</option>
                    <option value="amount">Amount (Cents)</option>
                  </select>
                </div>
                <div>
                  <label for="sec-match-type" class="block text-[11px] font-medium text-slate-600">2nd Condition</label>
                  <select
                    id="sec-match-type"
                    bind:value={secondaryMatchType}
                    class="mt-1 block w-full rounded border border-slate-300 px-2 py-1 text-xs text-slate-900"
                  >
                    <option value="contains">Contains</option>
                    <option value="exact">Exact Match</option>
                    <option value="starts_with">Starts With</option>
                  </select>
                </div>
                <div class="col-span-2">
                  <label for="sec-match-val" class="block text-[11px] font-medium text-slate-600">2nd Value</label>
                  <input
                    id="sec-match-val"
                    type="text"
                    bind:value={secondaryMatchValue}
                    placeholder="e.g. Payroll, Direct Dep, Store #123"
                    class="mt-1 block w-full rounded border border-slate-300 px-2 py-1 text-xs text-slate-900"
                  />
                </div>
              </div>
            {/if}
          </div>
        </div>

        <!-- Target Actions -->
        <div class="space-y-3 p-3 rounded-lg bg-indigo-50/50 border border-indigo-100">
          <h3 class="text-xs font-bold text-indigo-900 uppercase">2. Then Automatically Set:</h3>
          
          <div>
            <label for="target-payee-input" class="block text-xs font-medium text-slate-700">Cleaned Standard Payee Name</label>
            <input
              id="target-payee-input"
              type="text"
              bind:value={targetPayee}
              placeholder="e.g. Walmart"
              class="mt-1 block w-full rounded border border-slate-300 px-2.5 py-1.5 text-xs text-slate-900"
            />
          </div>

          <div>
            <label for="target-cat-select" class="block text-xs font-medium text-slate-700">Assigned Category</label>
            <select
              id="target-cat-select"
              bind:value={targetCategoryId}
              class="mt-1 block w-full rounded border border-slate-300 px-2.5 py-1.5 text-xs text-slate-900"
            >
              <option value="">-- Do Not Change Category --</option>
              {#each categoryGroups as group (group.id)}
                <optgroup label={group.name}>
                  {#each group.categories as cat (cat.id)}
                    <option value={cat.id}>{cat.name}</option>
                  {/each}
                </optgroup>
              {/each}
            </select>
          </div>
        </div>

        <!-- Rule Matching Preview & Count (US-3.7) -->
        <div class="p-3 rounded-lg bg-indigo-50/80 border border-indigo-200">
          <div class="flex items-center justify-between">
            <span class="text-xs font-bold text-indigo-900">Rule Match Preview (US-3.7):</span>
            {#if previewLoading}
              <span class="text-xs text-indigo-600 font-semibold animate-pulse">Checking matches...</span>
            {:else if previewMatchCount !== null}
              <span class="text-xs font-bold px-2 py-0.5 rounded bg-indigo-200 text-indigo-900">
                Matches {previewMatchCount} existing transaction{previewMatchCount === 1 ? '' : 's'}
              </span>
            {:else}
              <span class="text-xs text-slate-400 italic">Enter pattern to preview matches</span>
            {/if}
          </div>

          {#if previewSamples.length > 0}
            <div class="mt-2 text-[11px] space-y-1 max-h-24 overflow-y-auto font-mono text-slate-700 bg-white p-2 rounded border border-indigo-100">
              {#each previewSamples as sample (sample.id)}
                <div class="flex items-center justify-between border-b border-slate-100 pb-0.5">
                  <span class="truncate font-semibold">{sample.raw_payee}</span>
                  <span class="ml-2 font-bold text-slate-500">${(Math.abs(sample.amount_cents) / 100).toFixed(2)}</span>
                </div>
              {/each}
            </div>
          {/if}
        </div>

        <div class="grid grid-cols-2 gap-4 pt-1">
          <div>
            <label for="priority-input" class="block text-xs font-semibold text-slate-600 uppercase">Execution Priority</label>
            <input
              id="priority-input"
              type="number"
              min="1"
              bind:value={priority}
              class="mt-1 block w-full rounded border border-slate-300 px-2.5 py-1.5 text-xs text-slate-900"
            />
            <p class="text-[10px] text-slate-400 mt-0.5">Lower numbers execute first</p>
          </div>

          <div class="flex items-center space-x-2 pt-4">
            <input
              type="checkbox"
              id="is_active"
              bind:checked={isActive}
              class="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
            />
            <label for="is_active" class="text-xs font-semibold text-slate-700">
              Active Rule
            </label>
          </div>
        </div>

        <!-- US-3.2 Option: Apply Retroactively -->
        <div class="p-3 rounded-lg bg-amber-50 border border-amber-200">
          <label class="flex items-center text-xs font-bold text-amber-900 cursor-pointer select-none">
            <input
              type="checkbox"
              bind:checked={applyRetroactive}
              class="mr-2 h-4 w-4 rounded border-amber-400 text-amber-600 focus:ring-amber-500"
            />
            Apply retroactively to all existing historical transactions upon save (US-3.2)
          </label>
        </div>

        <div class="flex justify-end space-x-3 pt-4 border-t">
          <button
            type="button"
            onclick={handleClose}
            class="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={loading}
            class="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
          >
            {loading ? 'Saving...' : ruleToEdit ? 'Update Rule' : 'Save Rule'}
          </button>
        </div>
      </form>
    </div>
  </div>
{/if}

