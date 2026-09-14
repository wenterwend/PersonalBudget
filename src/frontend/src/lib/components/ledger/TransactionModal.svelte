<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { Account, CategoryGroup, Transaction, TransactionCreate, SplitInput } from '$lib/api';
  import { createTransaction, updateTransaction } from '$lib/api';
  import { centsToDollars, dollarsToCents, formatCents } from '$lib/utils/currency';

  let {
    show = false,
    transactionToEdit = null,
    accounts = [],
    categoryGroups = [],
    defaultAccountId = null,
  }: {
    show?: boolean;
    transactionToEdit?: Transaction | null;
    accounts?: Account[];
    categoryGroups?: CategoryGroup[];
    defaultAccountId?: string | null;
  } = $props();

  const dispatch = createEventDispatcher<{ save: Transaction; close: void }>();

  let accountId = $state('');
  let date = $state(new Date().toISOString().split('T')[0]);
  let rawPayee = $state('');
  let amountDollars = $state(0);
  let isExpense = $state(true);
  let cleared = $state(true);
  let notes = $state('');

  let isSplit = $state(false);
  let singleCategoryId = $state('');

  interface SplitRow {
    id: string;
    category_id: string;
    amount_dollars: number;
    notes: string;
  }
  let splitRows: SplitRow[] = $state([]);

  let error: string | null = $state(null);
  let loading = $state(false);

  let allCategories = $derived(categoryGroups.flatMap((g) => g.categories));

  $effect(() => {
    if (show) {
      if (transactionToEdit) {
        accountId = transactionToEdit.account_id;
        date = transactionToEdit.date;
        rawPayee = transactionToEdit.raw_payee;
        const absCents = Math.abs(transactionToEdit.amount_cents);
        amountDollars = centsToDollars(absCents);
        isExpense = transactionToEdit.amount_cents < 0;
        cleared = transactionToEdit.cleared;
        notes = transactionToEdit.notes || '';

        if (transactionToEdit.is_split && transactionToEdit.splits.length > 1) {
          isSplit = true;
          splitRows = transactionToEdit.splits.map((s) => ({
            id: s.id,
            category_id: s.category_id || '',
            amount_dollars: centsToDollars(Math.abs(s.amount_cents)),
            notes: s.notes || '',
          }));
        } else {
          isSplit = false;
          singleCategoryId = transactionToEdit.splits[0]?.category_id || '';
          splitRows = [];
        }
      } else {
        accountId = defaultAccountId || accounts[0]?.id || '';
        date = new Date().toISOString().split('T')[0];
        rawPayee = '';
        amountDollars = 0;
        isExpense = true;
        cleared = true;
        notes = '';
        isSplit = false;
        singleCategoryId = '';
        splitRows = [
          { id: crypto.randomUUID(), category_id: '', amount_dollars: 0, notes: '' },
          { id: crypto.randomUUID(), category_id: '', amount_dollars: 0, notes: '' },
        ];
      }
      error = null;
    }
  });

  let totalCents = $derived(dollarsToCents(amountDollars) * (isExpense ? -1 : 1));
  let splitSumCents = $derived(
    isSplit
      ? splitRows.reduce((sum, r) => sum + dollarsToCents(r.amount_dollars || 0) * (isExpense ? -1 : 1), 0)
      : totalCents
  );
  let splitDifferenceCents = $derived(totalCents - splitSumCents);
  let isSplitBalanced = $derived(!isSplit || splitDifferenceCents === 0);

  function toggleSplit() {
    isSplit = !isSplit;
    if (isSplit && splitRows.length === 0) {
      const halfDollars = amountDollars / 2;
      splitRows = [
        { id: crypto.randomUUID(), category_id: singleCategoryId || '', amount_dollars: halfDollars, notes: '' },
        { id: crypto.randomUUID(), category_id: '', amount_dollars: amountDollars - halfDollars, notes: '' },
      ];
    }
  }

  function addSplitRow() {
    splitRows = [...splitRows, { id: crypto.randomUUID(), category_id: '', amount_dollars: 0, notes: '' }];
  }

  function removeSplitRow(index: number) {
    if (splitRows.length <= 1) return;
    splitRows = splitRows.filter((_, i) => i !== index);
  }

  async function handleSubmit() {
    if (!accountId) {
      error = 'Please select an account.';
      return;
    }
    if (!rawPayee.trim()) {
      error = 'Payee name is required.';
      return;
    }
    if (amountDollars <= 0) {
      error = 'Please enter an amount greater than $0.00.';
      return;
    }
    if (isSplit && !isSplitBalanced) {
      error = `Split amounts sum does not match parent transaction total. Difference: ${formatCents(splitDifferenceCents)}`;
      return;
    }

    loading = true;
    error = null;

    try {
      let payloadSplits: SplitInput[] | undefined = undefined;
      if (isSplit) {
        payloadSplits = splitRows.map((r) => ({
          category_id: r.category_id || null,
          amount_cents: dollarsToCents(r.amount_dollars) * (isExpense ? -1 : 1),
          notes: r.notes.trim() || null,
        }));
      }

      const payload: TransactionCreate = {
        account_id: accountId,
        date,
        raw_payee: rawPayee.trim(),
        amount_cents: totalCents,
        notes: notes.trim() || undefined,
        cleared,
        category_id: !isSplit && singleCategoryId ? singleCategoryId : undefined,
        splits: payloadSplits,
      };

      let savedTx: Transaction;
      if (transactionToEdit) {
        savedTx = await updateTransaction(transactionToEdit.id, payload);
      } else {
        savedTx = await createTransaction(payload);
      }

      dispatch('save', savedTx);
      dispatch('close');
    } catch (e: any) {
      error = e.message || 'Failed to save transaction.';
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
    <div class="w-full max-w-xl rounded-xl bg-white p-6 shadow-2xl my-8">
      <div class="flex items-center justify-between pb-3 border-b">
        <h2 class="text-xl font-bold text-slate-800">
          {transactionToEdit ? 'Edit Transaction' : 'New Transaction'}
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
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label for="account-select" class="block text-xs font-semibold text-slate-600 uppercase">Account</label>
            <select
              id="account-select"
              bind:value={accountId}
              required
              class="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-slate-900 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              <option value="" disabled>Select Account</option>
              {#each accounts as acc (acc.id)}
                <option value={acc.id}>{acc.name} ({acc.type})</option>
              {/each}
            </select>
          </div>

          <div>
            <label for="tx-date-input" class="block text-xs font-semibold text-slate-600 uppercase">Date</label>
            <input
              id="tx-date-input"
              type="date"
              bind:value={date}
              required
              class="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-slate-900 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 items-end">
          <div class="sm:col-span-2">
            <label for="payee-input" class="block text-xs font-semibold text-slate-600 uppercase">Payee</label>
            <input
              id="payee-input"
              type="text"
              bind:value={rawPayee}
              placeholder="e.g. Target, Employer, Grocery Store"
              required
              class="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-slate-900 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          <div>
            <label for="type-toggle" class="block text-xs font-semibold text-slate-600 uppercase mb-1">Type</label>
            <div id="type-toggle" class="grid grid-cols-2 rounded-md bg-slate-100 p-1">
              <button
                type="button"
                onclick={() => (isExpense = true)}
                class={`rounded py-1 text-xs font-bold transition ${
                  isExpense ? 'bg-rose-600 text-white shadow-sm' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Expense
              </button>
              <button
                type="button"
                onclick={() => (isExpense = false)}
                class={`rounded py-1 text-xs font-bold transition ${
                  !isExpense ? 'bg-emerald-600 text-white shadow-sm' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Income
              </button>
            </div>
          </div>
        </div>

        <div>
          <label for="amount-input" class="block text-xs font-semibold text-slate-600 uppercase">Total Amount ($)</label>
          <input
            id="amount-input"
            type="number"
            step="0.01"
            min="0.01"
            bind:value={amountDollars}
            placeholder="0.00"
            required
            class="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-slate-900 text-lg font-bold shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
        </div>

        <!-- Category & Split Toggle -->
        <div class="border-t border-b border-slate-200 py-3 my-2">
          <div class="flex items-center justify-between mb-3">
            <span class="text-xs font-semibold text-slate-600 uppercase">Categorization</span>
            <button
              type="button"
              onclick={toggleSplit}
              class="text-xs font-bold text-indigo-600 hover:text-indigo-800 underline"
            >
              {isSplit ? 'Switch to Single Category' : 'Split Across Multiple Categories'}
            </button>
          </div>

          {#if !isSplit}
            <div>
              <label for="single-cat-select" class="block text-xs font-medium text-slate-600 mb-1">Category</label>
              <select
                id="single-cat-select"
                bind:value={singleCategoryId}
                class="block w-full rounded-md border border-slate-300 px-3 py-2 text-slate-900 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              >
                <option value="">-- Uncategorized --</option>
                {#each categoryGroups as group (group.id)}
                  <optgroup label={group.name}>
                    {#each group.categories as cat (cat.id)}
                      <option value={cat.id}>{cat.name}</option>
                    {/each}
                  </optgroup>
                {/each}
              </select>
            </div>
          {:else}
            <!-- Split Rows -->
            <div class="space-y-3">
              {#each splitRows as row, index (row.id)}
                <div class="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 p-2 rounded-lg bg-slate-50 border border-slate-200">
                  <select
                    bind:value={row.category_id}
                    class="flex-1 rounded border border-slate-300 px-2.5 py-1.5 text-xs text-slate-900 focus:ring-indigo-500"
                  >
                    <option value="">-- Uncategorized --</option>
                    {#each categoryGroups as group (group.id)}
                      <optgroup label={group.name}>
                        {#each group.categories as cat (cat.id)}
                          <option value={cat.id}>{cat.name}</option>
                        {/each}
                      </optgroup>
                    {/each}
                  </select>

                  <div class="flex items-center gap-1 w-full sm:w-32">
                    <span class="text-xs font-bold text-slate-500">$</span>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      bind:value={row.amount_dollars}
                      placeholder="0.00"
                      class="w-full rounded border border-slate-300 px-2 py-1 text-xs font-bold text-slate-900 focus:ring-indigo-500"
                    />
                  </div>

                  <input
                    type="text"
                    bind:value={row.notes}
                    placeholder="Row Note"
                    class="flex-1 rounded border border-slate-300 px-2 py-1 text-xs text-slate-700"
                  />

                  <button
                    type="button"
                    onclick={() => removeSplitRow(index)}
                    disabled={splitRows.length <= 1}
                    class="text-rose-500 hover:text-rose-700 text-xs font-bold p-1 disabled:opacity-30"
                  >
                    Delete
                  </button>
                </div>
              {/each}

              <div class="flex items-center justify-between pt-1">
                <button
                  type="button"
                  onclick={addSplitRow}
                  class="inline-flex items-center gap-1 text-xs font-bold text-indigo-600 hover:text-indigo-800"
                >
                  + Add Split Row
                </button>

                <!-- Live Split Validation Badge -->
                <div class={`text-xs font-bold px-2.5 py-1 rounded-full border ${
                  isSplitBalanced
                    ? 'bg-emerald-50 text-emerald-700 border-emerald-300'
                    : 'bg-rose-50 text-rose-700 border-rose-300'
                }`}>
                  {#if isSplitBalanced}
                    Splits Balanced ({formatCents(totalCents)})
                  {:else}
                    Unallocated: {formatCents(splitDifferenceCents)}
                  {/if}
                </div>
              </div>
            </div>
          {/if}
        </div>

        <div>
          <label for="notes-input" class="block text-xs font-semibold text-slate-600 uppercase">Notes</label>
          <input
            id="notes-input"
            type="text"
            bind:value={notes}
            placeholder="Optional transaction details"
            class="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-slate-900 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
        </div>

        <div class="flex items-center space-x-2 pt-1">
          <input
            type="checkbox"
            id="cleared"
            bind:checked={cleared}
            class="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
          />
          <label for="cleared" class="text-sm font-medium text-slate-700">
            Cleared Transaction
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
            disabled={loading || (isSplit && !isSplitBalanced)}
            class="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
          >
            {loading ? 'Saving...' : transactionToEdit ? 'Update Transaction' : 'Save Transaction'}
          </button>
        </div>
      </form>
    </div>
  </div>
{/if}
