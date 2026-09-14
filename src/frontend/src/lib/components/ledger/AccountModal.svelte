<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { type Account, type AccountCreate, createAccount, updateAccount } from '$lib/api';
  import { dollarsToCents, centsToDollars } from '$lib/utils/currency';

  let {
    show = false,
    accountToEdit = null,
  }: {
    show?: boolean;
    accountToEdit?: Account | null;
  } = $props();

  const dispatch = createEventDispatcher<{ save: Account; close: void }>();

  let name = $state('');
  let type: 'checking' | 'savings' | 'credit' | 'investment' = $state('checking');
  let currency = $state('USD');
  let openingBalanceDollars = $state(0);
  let openingDate = $state(new Date().toISOString().split('T')[0]);
  let isClosed = $state(false);
  let error: string | null = $state(null);
  let loading = $state(false);

  $effect(() => {
    if (show) {
      if (accountToEdit) {
        name = accountToEdit.name;
        type = accountToEdit.type;
        currency = accountToEdit.currency;
        openingBalanceDollars = centsToDollars(accountToEdit.opening_balance_cents);
        openingDate = accountToEdit.opening_date;
        isClosed = accountToEdit.is_closed;
      } else {
        name = '';
        type = 'checking';
        currency = 'USD';
        openingBalanceDollars = 0;
        openingDate = new Date().toISOString().split('T')[0];
        isClosed = false;
      }
      error = null;
    }
  });

  async function handleSubmit() {
    if (!name.trim()) {
      error = 'Account name is required.';
      return;
    }
    loading = true;
    error = null;

    try {
      const payload: AccountCreate = {
        name: name.trim(),
        type,
        currency,
        opening_balance_cents: dollarsToCents(openingBalanceDollars),
        opening_date: openingDate,
        is_closed: isClosed,
      };

      let savedAccount: Account;
      if (accountToEdit) {
        savedAccount = await updateAccount(accountToEdit.id, payload);
      } else {
        savedAccount = await createAccount(payload);
      }

      dispatch('save', savedAccount);
      dispatch('close');
    } catch (e: any) {
      error = e.message || 'Failed to save account.';
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
    <div class="w-full max-w-md rounded-xl bg-white p-6 shadow-2xl">
      <div class="flex items-center justify-between pb-3 border-b">
        <h2 class="text-xl font-bold text-slate-800">
          {accountToEdit ? 'Edit Account' : 'Create New Account'}
        </h2>
        <button
          type="button"
          onclick={handleClose}
          class="text-slate-400 hover:text-slate-600 text-2xl font-semibold"
        >&times;</button>
      </div>

      {#if error}
        <div class="mt-4 p-3 rounded-lg bg-red-50 text-red-700 text-sm font-medium border border-red-200">
          {error}
        </div>
      {/if}

      <form onsubmit={(e) => { e.preventDefault(); handleSubmit(); }} class="mt-4 space-y-4">
        <div>
          <label for="name-input" class="block text-sm font-medium text-slate-700">Account Name</label>
          <input
            id="name-input"
            type="text"
            bind:value={name}
            placeholder="e.g. Primary Checking"
            required
            class="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-slate-900 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
        </div>

        <div>
          <label for="type-select" class="block text-sm font-medium text-slate-700">Account Type</label>
          <select
            id="type-select"
            bind:value={type}
            class="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-slate-900 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          >
            <option value="checking">Checking</option>
            <option value="savings">Savings</option>
            <option value="credit">Credit Card</option>
            <option value="investment">Investment</option>
          </select>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div>
            <label for="opening-balance-input" class="block text-sm font-medium text-slate-700">Opening Balance ($)</label>
            <input
              id="opening-balance-input"
              type="number"
              step="0.01"
              bind:value={openingBalanceDollars}
              class="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-slate-900 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          <div>
            <label for="opening-date-input" class="block text-sm font-medium text-slate-700">Opening Date</label>
            <input
              id="opening-date-input"
              type="date"
              bind:value={openingDate}
              required
              class="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-slate-900 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>
        </div>

        {#if accountToEdit}
          <div class="flex items-center space-x-2 pt-2">
            <input
              type="checkbox"
              id="is_closed"
              bind:checked={isClosed}
              class="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
            />
            <label for="is_closed" class="text-sm font-medium text-slate-700">
              Close / Archive Account
            </label>
          </div>
        {/if}

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
            {loading ? 'Saving...' : accountToEdit ? 'Update Account' : 'Create Account'}
          </button>
        </div>
      </form>
    </div>
  </div>
{/if}
