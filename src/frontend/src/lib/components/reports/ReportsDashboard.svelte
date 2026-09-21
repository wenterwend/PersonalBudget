<script lang="ts">
  import { onMount } from 'svelte';
  import {
    getSpendingByCategory,
    getIncomeVsExpense,
    getNetWorthHistory,
    getCategoryInitiators,
    type SpendingByCategoryResponse,
    type IncomeVsExpenseResponse,
    type NetWorthResponse,
    type CategoryInitiatorResponse,
  } from '$lib/api';
  import { formatCents } from '$lib/utils/currency';

  let dateFilter: 'this_month' | 'last_3_months' | 'year_to_date' | 'q1' | 'q2' | 'q3' | 'q4' | 'custom' | 'all' = $state('this_month');
  let startDate = $state('');
  let endDate = $state('');

  let spendingData: SpendingByCategoryResponse | null = $state(null);
  let incomeVsExpenseData: IncomeVsExpenseResponse | null = $state(null);
  let netWorthData: NetWorthResponse | null = $state(null);
  let loading = $state(false);

  // US-5.7 Category Breakdown State
  let showInitiatorModal = $state(false);
  let selectedCategoryName = $state('');
  let initiatorData: CategoryInitiatorResponse | null = $state(null);
  let loadingInitiators = $state(false);

  // Palette for SVG chart categories
  const categoryColors = [
    '#4f46e5', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
    '#06b6d4', '#ec4899', '#64748b', '#84cc16', '#3b82f6',
  ];

  onMount(() => {
    applyPreset('this_month');
  });

  function applyPreset(preset: 'this_month' | 'last_3_months' | 'year_to_date' | 'q1' | 'q2' | 'q3' | 'q4' | 'all') {
    dateFilter = preset;
    const now = new Date();
    const year = now.getFullYear();

    if (preset === 'this_month') {
      const month = String(now.getMonth() + 1).padStart(2, '0');
      startDate = `${year}-${month}-01`;
      endDate = '';
    } else if (preset === 'last_3_months') {
      const past = new Date();
      past.setMonth(past.getMonth() - 3);
      startDate = past.toISOString().slice(0, 10);
      endDate = '';
    } else if (preset === 'year_to_date') {
      startDate = `${year}-01-01`;
      endDate = '';
    } else if (preset === 'q1') {
      startDate = `${year}-01-01`;
      endDate = `${year}-03-31`;
    } else if (preset === 'q2') {
      startDate = `${year}-04-01`;
      endDate = `${year}-06-30`;
    } else if (preset === 'q3') {
      startDate = `${year}-07-01`;
      endDate = `${year}-09-30`;
    } else if (preset === 'q4') {
      startDate = `${year}-10-01`;
      endDate = `${year}-12-31`;
    } else {
      startDate = '';
      endDate = '';
    }
    loadReportsData();
  }

  function handleCustomDateChange() {
    dateFilter = 'custom';
    loadReportsData();
  }

  async function loadReportsData() {
    loading = true;
    try {
      const [spending, incExp, nw] = await Promise.all([
        getSpendingByCategory(startDate || undefined, endDate || undefined),
        getIncomeVsExpense(startDate || undefined, endDate || undefined),
        getNetWorthHistory(),
      ]);
      spendingData = spending;
      incomeVsExpenseData = incExp;
      netWorthData = nw;
    } catch (e) {
      console.error('Failed to load reports data:', e);
    } finally {
      loading = false;
    }
  }

  async function openInitiatorBreakdown(catId: string, catName: string) {
    selectedCategoryName = catName;
    showInitiatorModal = true;
    loadingInitiators = true;
    try {
      initiatorData = await getCategoryInitiators(catId, startDate || undefined, endDate || undefined);
    } catch (e) {
      console.error('Failed to load initiator breakdown:', e);
      initiatorData = null;
    } finally {
      loadingInitiators = false;
    }
  }

  function handlePrint() {
    window.print();
  }

  let savingsRate = $derived.by(() => {
    if (!incomeVsExpenseData || incomeVsExpenseData.total_income_cents <= 0) return 0;
    const rate = (incomeVsExpenseData.total_net_savings_cents / incomeVsExpenseData.total_income_cents) * 100;
    return Math.max(0, Math.round(rate * 10) / 10);
  });
</script>

<div class="space-y-6">
  <!-- Top Action & Filter Bar (Hidden when printing) -->
  <div class="no-print bg-white p-4 rounded-2xl border border-slate-200 shadow-sm flex flex-col xl:flex-row items-start xl:items-center justify-between gap-4">
    <!-- Date Range Quick Presets & Custom Selector (US-5.8) -->
    <div class="flex flex-wrap items-center gap-3">
      <span class="text-xs font-bold text-slate-500 uppercase tracking-wider">Period:</span>
      
      <div class="inline-flex flex-wrap rounded-xl bg-slate-100 p-1 text-xs font-bold gap-0.5">
        <button
          type="button"
          onclick={() => applyPreset('this_month')}
          class={`px-2.5 py-1 rounded-lg transition ${dateFilter === 'this_month' ? 'bg-white text-indigo-700 shadow-xs' : 'text-slate-600 hover:text-slate-900'}`}
        >
          This Month
        </button>
        <button
          type="button"
          onclick={() => applyPreset('last_3_months')}
          class={`px-2.5 py-1 rounded-lg transition ${dateFilter === 'last_3_months' ? 'bg-white text-indigo-700 shadow-xs' : 'text-slate-600 hover:text-slate-900'}`}
        >
          3 Months
        </button>
        <button
          type="button"
          onclick={() => applyPreset('year_to_date')}
          class={`px-2.5 py-1 rounded-lg transition ${dateFilter === 'year_to_date' ? 'bg-white text-indigo-700 shadow-xs' : 'text-slate-600 hover:text-slate-900'}`}
        >
          YTD
        </button>
        <button
          type="button"
          onclick={() => applyPreset('q1')}
          class={`px-2 py-1 rounded-lg transition ${dateFilter === 'q1' ? 'bg-white text-indigo-700 shadow-xs' : 'text-slate-600 hover:text-slate-900'}`}
        >
          Q1
        </button>
        <button
          type="button"
          onclick={() => applyPreset('q2')}
          class={`px-2 py-1 rounded-lg transition ${dateFilter === 'q2' ? 'bg-white text-indigo-700 shadow-xs' : 'text-slate-600 hover:text-slate-900'}`}
        >
          Q2
        </button>
        <button
          type="button"
          onclick={() => applyPreset('q3')}
          class={`px-2 py-1 rounded-lg transition ${dateFilter === 'q3' ? 'bg-white text-indigo-700 shadow-xs' : 'text-slate-600 hover:text-slate-900'}`}
        >
          Q3
        </button>
        <button
          type="button"
          onclick={() => applyPreset('q4')}
          class={`px-2 py-1 rounded-lg transition ${dateFilter === 'q4' ? 'bg-white text-indigo-700 shadow-xs' : 'text-slate-600 hover:text-slate-900'}`}
        >
          Q4
        </button>
        <button
          type="button"
          onclick={() => applyPreset('all')}
          class={`px-2.5 py-1 rounded-lg transition ${dateFilter === 'all' ? 'bg-white text-indigo-700 shadow-xs' : 'text-slate-600 hover:text-slate-900'}`}
        >
          All Time
        </button>
      </div>

      <!-- US-5.8 Custom Date Inputs -->
      <div class="flex items-center gap-1.5 text-xs">
        <span class="font-bold text-slate-400">From:</span>
        <input
          type="date"
          bind:value={startDate}
          onchange={handleCustomDateChange}
          class="rounded-lg border border-slate-300 bg-slate-50 px-2 py-1 text-xs font-semibold text-slate-800"
        />
        <span class="font-bold text-slate-400">To:</span>
        <input
          type="date"
          bind:value={endDate}
          onchange={handleCustomDateChange}
          class="rounded-lg border border-slate-300 bg-slate-50 px-2 py-1 text-xs font-semibold text-slate-800"
        />
      </div>
    </div>

    <!-- Print Report Action -->
    <button
      type="button"
      onclick={handlePrint}
      class="inline-flex items-center gap-2 rounded-xl border border-slate-300 bg-white px-4 py-2 text-xs font-bold text-slate-800 shadow-xs hover:bg-slate-50 active:scale-95 transition"
    >
      <span>🖨️ Print Report / Save PDF</span>
    </button>
  </div>

  <!-- Report Header (Visible on print layout) -->
  <div class="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm print:shadow-none print:border-none">
    <div class="flex items-center justify-between border-b pb-4">
      <div>
        <h1 class="text-2xl font-black text-slate-900 tracking-tight">Financial Trends & Analytics Report</h1>
        <p class="text-xs text-slate-500 mt-0.5">
          Generated on {new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}
        </p>
      </div>
      <div class="text-right">
        <span class="text-xs font-bold uppercase tracking-wider text-slate-400">Household Ledger</span>
        <div class="text-sm font-bold text-slate-700">Personal Finance System</div>
      </div>
    </div>

    <!-- Key Financial Summary Metrics -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mt-6">
      <div class="p-4 rounded-2xl bg-indigo-50/70 border border-indigo-100">
        <span class="text-[10px] font-extrabold uppercase tracking-wider text-indigo-600">Net Worth</span>
        <div class="text-xl font-black text-indigo-950 mt-1">
          {netWorthData ? formatCents(netWorthData.net_worth_cents) : '$0.00'}
        </div>
      </div>

      <div class="p-4 rounded-2xl bg-emerald-50/70 border border-emerald-100">
        <span class="text-[10px] font-extrabold uppercase tracking-wider text-emerald-700">Total Period Income</span>
        <div class="text-xl font-black text-emerald-950 mt-1">
          {incomeVsExpenseData ? formatCents(incomeVsExpenseData.total_income_cents) : '$0.00'}
        </div>
      </div>

      <div class="p-4 rounded-2xl bg-rose-50/70 border border-rose-100">
        <span class="text-[10px] font-extrabold uppercase tracking-wider text-rose-700">Total Period Expenses</span>
        <div class="text-xl font-black text-rose-950 mt-1">
          {incomeVsExpenseData ? formatCents(incomeVsExpenseData.total_expense_cents) : '$0.00'}
        </div>
      </div>

      <div class="p-4 rounded-2xl bg-slate-100 border border-slate-200">
        <span class="text-[10px] font-extrabold uppercase tracking-wider text-slate-600">Net Savings Rate</span>
        <div class="text-xl font-black text-slate-900 mt-1">
          {savingsRate}%
        </div>
      </div>
    </div>
  </div>

  {#if loading}
    <div class="p-12 text-center text-slate-500 font-semibold text-sm bg-white rounded-2xl border">
      Loading financial analytics...
    </div>
  {:else}
    <!-- Two Column Analytics Grid -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <!-- Category Spending Breakdown (US-5.3) -->
      <div class="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-4 print:break-inside-avoid">
        <div class="flex items-center justify-between border-b pb-3">
          <h3 class="text-base font-bold text-slate-900">Spending by Category</h3>
          <span class="text-xs font-bold text-slate-500">
            Total: {spendingData ? formatCents(spendingData.total_expense_cents) : '$0.00'}
          </span>
        </div>

        {#if !spendingData || spendingData.categories.length === 0}
          <div class="p-6 text-center text-slate-400 text-xs font-semibold">
            No expense data found for selected period.
          </div>
        {:else}
          <div class="space-y-3">
            {#each spendingData.categories.slice(0, 8) as cat, idx}
              <button
                type="button"
                onclick={() => openInitiatorBreakdown(cat.category_id, cat.category_name)}
                class="w-full text-left space-y-1 text-xs p-2 rounded-xl hover:bg-slate-50 transition border border-transparent hover:border-slate-200 group"
                title="Click to view category breakdown by transaction initiator"
              >
                <div class="flex items-center justify-between font-bold text-slate-800">
                  <div class="flex items-center gap-2">
                    <span
                      class="h-3 w-3 rounded-full shrink-0"
                      style="background-color: {categoryColors[idx % categoryColors.length]}"
                    ></span>
                    <span class="group-hover:text-indigo-600 group-hover:underline">{cat.category_name}</span>
                    <span class="text-[10px] font-semibold text-slate-400">({cat.group_name})</span>
                  </div>
                  <div class="flex items-center gap-2">
                    <span>{formatCents(cat.total_cents)}</span>
                    <span class="text-slate-400 font-mono text-[10px]">({cat.percentage}%)</span>
                    <span class="text-[10px] font-extrabold text-indigo-500 opacity-0 group-hover:opacity-100 transition">🔍 Initiators</span>
                  </div>
                </div>
                <!-- SVG Progress Bar -->
                <div class="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
                  <div
                    class="h-full rounded-full transition-all duration-500"
                    style="width: {cat.percentage}%; background-color: {categoryColors[idx % categoryColors.length]}"
                  ></div>
                </div>
              </button>
            {/each}
          </div>
        {/if}
      </div>

      <!-- Monthly Income vs Expense Chart (US-5.3) -->
      <div class="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-4 print:break-inside-avoid">
        <div class="flex items-center justify-between border-b pb-3">
          <h3 class="text-base font-bold text-slate-900">Monthly Cashflow Trend</h3>
          <div class="flex items-center gap-3 text-xs font-bold">
            <span class="flex items-center gap-1"><span class="h-2.5 w-2.5 rounded bg-emerald-500"></span> Income</span>
            <span class="flex items-center gap-1"><span class="h-2.5 w-2.5 rounded bg-slate-800"></span> Expense</span>
          </div>
        </div>

        {#if !incomeVsExpenseData || incomeVsExpenseData.months.length === 0}
          <div class="p-6 text-center text-slate-400 text-xs font-semibold">
            No monthly cashflow trends available for selected period.
          </div>
        {:else}
          <div class="space-y-4">
            <div class="space-y-3">
              {#each incomeVsExpenseData.months as m}
                {@const maxVal = Math.max(m.income_cents, m.expense_cents, 1)}
                {@const incPct = Math.round((m.income_cents / maxVal) * 100)}
                {@const expPct = Math.round((m.expense_cents / maxVal) * 100)}
                <div class="space-y-1 text-xs">
                  <div class="flex items-center justify-between font-bold text-slate-800">
                    <span class="font-mono">{m.month}</span>
                    <span class={`font-mono ${m.net_savings_cents >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
                      Net: {formatCents(m.net_savings_cents)}
                    </span>
                  </div>

                  <!-- Dual Bar Chart -->
                  <div class="space-y-1">
                    <div class="flex items-center gap-2">
                      <span class="w-12 text-[10px] text-slate-400 font-semibold">Inc</span>
                      <div class="h-2.5 flex-1 bg-slate-100 rounded-full overflow-hidden">
                        <div class="h-full bg-emerald-500 rounded-full" style="width: {incPct}%"></div>
                      </div>
                      <span class="w-16 text-right font-mono text-[10px] text-emerald-700 font-bold">{formatCents(m.income_cents)}</span>
                    </div>

                    <div class="flex items-center gap-2">
                      <span class="w-12 text-[10px] text-slate-400 font-semibold">Exp</span>
                      <div class="h-2.5 flex-1 bg-slate-100 rounded-full overflow-hidden">
                        <div class="h-full bg-slate-800 rounded-full" style="width: {expPct}%"></div>
                      </div>
                      <span class="w-16 text-right font-mono text-[10px] text-slate-800 font-bold">{formatCents(m.expense_cents)}</span>
                    </div>
                  </div>
                </div>
              {/each}
            </div>
          </div>
        {/if}
      </div>
    </div>

    <!-- Account Net Worth Breakdown -->
    {#if netWorthData}
      <div class="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-4 print:break-inside-avoid">
        <h3 class="text-base font-bold text-slate-900 border-b pb-3">Account Balances & Asset Breakdown</h3>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {#each netWorthData.accounts as acc}
            <div class="p-3.5 rounded-xl border border-slate-200 bg-slate-50/60 space-y-1">
              <span class="text-[10px] font-extrabold uppercase tracking-wider text-slate-500">
                {acc.name} &bull; {acc.type}
              </span>
              <div class={`text-lg font-black ${acc.current_balance_cents >= 0 ? 'text-slate-900' : 'text-rose-600'}`}>
                {formatCents(acc.current_balance_cents)}
              </div>
            </div>
          {/each}
        </div>
      </div>
    {/if}
  {/if}

  <!-- US-5.7 Initiator Breakdown Modal -->
  {#if showInitiatorModal}
    <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 no-print">
      <div class="w-full max-w-xl rounded-2xl bg-white p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
        <div class="flex items-center justify-between border-b pb-3">
          <div>
            <h3 class="text-lg font-bold text-slate-900">Initiator Breakdown: {selectedCategoryName}</h3>
            <p class="text-xs text-slate-500">Proportion of category spending attributed to each merchant/payee (US-5.7)</p>
          </div>
          <button
            type="button"
            onclick={() => (showInitiatorModal = false)}
            class="text-slate-400 hover:text-slate-600 text-2xl font-bold px-2"
          >
            &times;
          </button>
        </div>

        {#if loadingInitiators}
          <div class="p-8 text-center text-slate-500 text-xs font-semibold">
            Loading initiator breakdown data...
          </div>
        {:else if !initiatorData || initiatorData.initiators.length === 0}
          <div class="p-8 text-center text-slate-400 text-xs font-semibold">
            No transactions found for this category in the selected period.
          </div>
        {:else}
          <div class="space-y-4">
            <div class="p-3 bg-indigo-50 border border-indigo-100 rounded-xl flex items-center justify-between text-xs font-bold text-indigo-950">
              <span>Total Spent in Category:</span>
              <span class="text-sm font-black">{formatCents(initiatorData.total_expense_cents)}</span>
            </div>

            <div class="space-y-3">
              {#each initiatorData.initiators as item, idx}
                <div class="p-3 rounded-xl border border-slate-200 bg-slate-50/70 space-y-1.5">
                  <div class="flex items-center justify-between font-bold text-xs text-slate-900">
                    <span class="truncate max-w-[240px]">{item.payee}</span>
                    <div class="flex items-center gap-2">
                      <span>{formatCents(item.total_cents)}</span>
                      <span class="text-slate-400 text-[10px]">({item.percentage}%)</span>
                    </div>
                  </div>
                  <div class="flex items-center justify-between text-[10px] text-slate-500 font-semibold">
                    <span>{item.transaction_count} transaction{item.transaction_count === 1 ? '' : 's'}</span>
                  </div>
                  <div class="h-2 w-full bg-slate-200 rounded-full overflow-hidden">
                    <div
                      class="h-full bg-indigo-600 rounded-full transition-all duration-300"
                      style="width: {item.percentage}%"
                    ></div>
                  </div>
                </div>
              {/each}
            </div>
          </div>
        {/if}

        <div class="flex justify-end pt-2">
          <button
            type="button"
            onclick={() => (showInitiatorModal = false)}
            class="rounded-xl border border-slate-300 bg-white px-4 py-1.5 text-xs font-bold text-slate-700 hover:bg-slate-50"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  {/if}
</div>

