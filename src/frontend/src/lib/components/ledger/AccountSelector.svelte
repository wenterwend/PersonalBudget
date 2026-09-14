<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { Account } from '$lib/api';
  import { formatCents } from '$lib/utils/currency';

  let {
    accounts = [],
    selectedAccountId = null,
    includeClosed = false,
  }: {
    accounts?: Account[];
    selectedAccountId?: string | null;
    includeClosed?: boolean;
  } = $props();

  const dispatch = createEventDispatcher<{
    select: string | null;
    createAccount: void;
    editAccount: Account;
    toggleIncludeClosed: boolean;
  }>();

  let totalBalanceCents = $derived(accounts.reduce((sum, a) => sum + a.current_balance_cents, 0));

  function selectAccount(id: string | null) {
    dispatch('select', id);
  }

  function handleAddAccount() {
    dispatch('createAccount');
  }

  function handleEditAccount(account: Account, event: MouseEvent) {
    event.stopPropagation();
    dispatch('editAccount', account);
  }
</script>

<div class="bg-white rounded-xl p-4 shadow-sm border border-slate-200 mb-6">
  <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-3 border-b border-slate-100">
    <div>
      <h2 class="text-lg font-bold text-slate-800">Accounts Overview</h2>
      <p class="text-xs text-slate-500">Select an account or view unified ledger</p>
    </div>
    
    <div class="flex items-center gap-3 w-full sm:w-auto justify-between sm:justify-end">
      <label class="flex items-center text-xs text-slate-600 cursor-pointer select-none">
        <input
          type="checkbox"
          checked={includeClosed}
          onchange={(e) => dispatch('toggleIncludeClosed', e.currentTarget.checked)}
          class="mr-1.5 h-3.5 w-3.5 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
        />
        Show Archived
      </label>

      <button
        type="button"
        onclick={handleAddAccount}
        class="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-indigo-700 transition"
      >
        <span class="text-base font-bold leading-none">+</span> Add Account
      </button>
    </div>
  </div>

  <div class="mt-4 flex flex-wrap gap-2">
    <!-- All Accounts Button -->
    <button
      type="button"
      onclick={() => selectAccount(null)}
      class={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition border ${
        selectedAccountId === null
          ? 'bg-indigo-50 border-indigo-500 text-indigo-700 shadow-sm'
          : 'bg-slate-50 border-slate-200 text-slate-700 hover:bg-slate-100'
      }`}
    >
      <span>All Accounts</span>
      <span class={`text-xs px-2 py-0.5 rounded-full font-bold ${
        totalBalanceCents >= 0 ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800'
      }`}>
        {formatCents(totalBalanceCents)}
      </span>
    </button>

    <!-- Individual Accounts -->
    {#each accounts as account (account.id)}
      <div
        role="button"
        tabindex="0"
        onclick={() => selectAccount(account.id)}
        onkeydown={(e) => e.key === 'Enter' && selectAccount(account.id)}
        class={`group relative flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium cursor-pointer transition border ${
          selectedAccountId === account.id
            ? 'bg-indigo-50 border-indigo-500 text-indigo-700 shadow-sm'
            : 'bg-slate-50 border-slate-200 text-slate-700 hover:bg-slate-100'
        } ${account.is_closed ? 'opacity-60 italic' : ''}`}
      >
        <span class="truncate max-w-[140px]">{account.name}</span>
        
        <span class={`text-xs px-2 py-0.5 rounded-full font-bold ${
          account.current_balance_cents >= 0 ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800'
        }`}>
          {formatCents(account.current_balance_cents, account.currency)}
        </span>

        <button
          type="button"
          title="Edit Account"
          onclick={(e) => handleEditAccount(account, e)}
          class="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-slate-200 text-slate-500 transition"
        >
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/>
          </svg>
        </button>
      </div>
    {/each}
  </div>
</div>
