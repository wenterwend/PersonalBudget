<script lang="ts">
  import { onMount } from 'svelte';
  import {
    getSpendingByCategory,
    getIncomeVsExpense,
    getNetWorthHistory,
    getCategoryInitiators,
    getInitiatorTransactions,
    getMonthOverMonthComparison,
    getFixedVsVariableReport,
    getSpendingHeatmap,
    getTopMerchants,
    getRecurringSubscriptions,
    getBudgetVariance,
    getSavingsRateRunway,
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
  let monthOverMonthData: any | null = $state(null);
  let fixedVsVariableData: any | null = $state(null);
  let heatmapData: any | null = $state(null);
  let topMerchantsData: any | null = $state(null);
  let subscriptionsData: any | null = $state(null);
  let budgetVarianceData: any | null = $state(null);
  let savingsRunwayData: any | null = $state(null);
  let loading = $state(false);

  // US-5.7 & US-5.10 Initiator & Transaction Drill-down State
  let showInitiatorModal = $state(false);
  let selectedCategoryId = $state('');
  let selectedCategoryName = $state('');
  let initiatorData: CategoryInitiatorResponse | null = $state(null);
  let loadingInitiators = $state(false);

  let showDrilldownModal = $state(false);
  let drilldownPayee = $state('');
  let drilldownTransactions: any[] = $state([]);
  let loadingDrilldown = $state(false);

  // Leaderboard Sort Toggle (US-5.14)
  let merchantSortBy: 'total_amount' | 'frequency' = $state('total_amount');

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
    const currentMonth = new Date().toISOString().slice(0, 7);
    try {
      const [spending, incExp, nw, mom, fvv, hmap, merchants, subs, variance, sr] = await Promise.all([
        getSpendingByCategory(startDate || undefined, endDate || undefined),
        getIncomeVsExpense(startDate || undefined, endDate || undefined),
        getNetWorthHistory(),
        getMonthOverMonthComparison(undefined, 6, startDate || undefined, endDate || undefined),
        getFixedVsVariableReport(startDate || undefined, endDate || undefined),
        getSpendingHeatmap(startDate || undefined, endDate || undefined),
        getTopMerchants(10, merchantSortBy, startDate || undefined, endDate || undefined),
        getRecurringSubscriptions(),
        getBudgetVariance(currentMonth),
        getSavingsRateRunway(6),
      ]);
      spendingData = spending;
      incomeVsExpenseData = incExp;
      netWorthData = nw;
      monthOverMonthData = mom;
      fixedVsVariableData = fvv;
      heatmapData = hmap;
      topMerchantsData = merchants;
      subscriptionsData = subs;
      budgetVarianceData = variance;
      savingsRunwayData = sr;
    } catch (e) {
      console.error('Failed to load reports data:', e);
    } finally {
      loading = false;
    }
  }

  async function handleMerchantSortChange(newSort: 'total_amount' | 'frequency') {
    merchantSortBy = newSort;
    try {
      topMerchantsData = await getTopMerchants(10, merchantSortBy, startDate || undefined, endDate || undefined);
    } catch (e) {
      console.error('Failed to load top merchants:', e);
    }
  }

  async function openInitiatorBreakdown(catId: string, catName: string) {
    selectedCategoryId = catId;
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

  async function openDrilldownModal(payee: string) {
    drilldownPayee = payee;
    showDrilldownModal = true;
    loadingDrilldown = true;
    try {
      const res = await getInitiatorTransactions(selectedCategoryId, payee, startDate || undefined, endDate || undefined);
      drilldownTransactions = res.transactions;
    } catch (e) {
      console.error('Failed to load drilldown transactions:', e);
      drilldownTransactions = [];
    } finally {
      loadingDrilldown = false;
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

      <!-- US-5.17 Savings Rate & Liquid Runway Card -->
      <div class="p-4 rounded-2xl bg-slate-100 border border-slate-200">
        <div class="flex items-center justify-between">
          <span class="text-[10px] font-extrabold uppercase tracking-wider text-slate-600">Net Savings Rate</span>
          <span class="text-[9px] font-extrabold px-1.5 py-0.5 rounded bg-indigo-100 text-indigo-800">
            Runway: {savingsRunwayData ? `${savingsRunwayData.estimated_runway_months} mo` : '&mdash;'}
          </span>
        </div>
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

    <!-- US-5.12 Fixed vs Variable Expense Breakdown & US-5.14 Top Merchants Leaderboard -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <!-- US-5.12 Fixed vs Variable Breakdown -->
      {#if fixedVsVariableData}
        <div class="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-4 print:break-inside-avoid">
          <div class="flex items-center justify-between border-b pb-3">
            <h3 class="text-base font-bold text-slate-900">Fixed vs. Variable Expenses</h3>
            <span class="text-xs font-extrabold text-slate-500">
              Total: {formatCents(fixedVsVariableData.total_expense_cents)}
            </span>
          </div>

          <div class="space-y-4">
            <!-- Progress Bar split -->
            <div class="h-3 w-full bg-slate-100 rounded-full overflow-hidden flex">
              <div
                class="h-full bg-indigo-600 transition-all duration-500"
                style="width: {fixedVsVariableData.fixed_percentage}%"
                title="Fixed Expenses: {fixedVsVariableData.fixed_percentage}%"
              ></div>
              <div
                class="h-full bg-emerald-500 transition-all duration-500"
                style="width: {fixedVsVariableData.variable_percentage}%"
                title="Variable Expenses: {fixedVsVariableData.variable_percentage}%"
              ></div>
            </div>

            <div class="grid grid-cols-2 gap-4">
              <div class="p-3 bg-indigo-50/70 border border-indigo-100 rounded-xl space-y-1">
                <span class="text-[10px] font-extrabold uppercase tracking-wider text-indigo-700">Fixed (Mandatory)</span>
                <div class="text-base font-black text-indigo-950">
                  {formatCents(fixedVsVariableData.fixed_expense_cents)}
                  <span class="text-xs font-bold text-indigo-600">({fixedVsVariableData.fixed_percentage}%)</span>
                </div>
              </div>

              <div class="p-3 bg-emerald-50/70 border border-emerald-100 rounded-xl space-y-1">
                <span class="text-[10px] font-extrabold uppercase tracking-wider text-emerald-700">Variable (Discretionary)</span>
                <div class="text-base font-black text-emerald-950">
                  {formatCents(fixedVsVariableData.variable_expense_cents)}
                  <span class="text-xs font-bold text-emerald-600">({fixedVsVariableData.variable_percentage}%)</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      {/if}

      <!-- US-5.14 Top Merchant Leaderboard -->
      {#if topMerchantsData}
        <div class="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-4 print:break-inside-avoid">
          <div class="flex items-center justify-between border-b pb-3">
            <h3 class="text-base font-bold text-slate-900">Top Merchant Leaderboard</h3>
            <div class="inline-flex rounded-lg bg-slate-100 p-0.5 text-[11px] font-bold">
              <button
                type="button"
                onclick={() => handleMerchantSortChange('total_amount')}
                class={`px-2 py-0.5 rounded transition ${merchantSortBy === 'total_amount' ? 'bg-white text-indigo-700 shadow-xs' : 'text-slate-600'}`}
              >
                By Amount
              </button>
              <button
                type="button"
                onclick={() => handleMerchantSortChange('frequency')}
                class={`px-2 py-0.5 rounded transition ${merchantSortBy === 'frequency' ? 'bg-white text-indigo-700 shadow-xs' : 'text-slate-600'}`}
              >
                By Frequency
              </button>
            </div>
          </div>

          <div class="space-y-2 text-xs">
            {#each topMerchantsData.merchants as m, idx}
              <div class="flex items-center justify-between p-2 rounded-xl border border-slate-100 bg-slate-50/60 font-medium">
                <div class="flex items-center gap-2">
                  <span class="h-5 w-5 rounded-full bg-slate-200 text-slate-700 text-[10px] font-black flex items-center justify-center">
                    {idx + 1}
                  </span>
                  <div>
                    <span class="font-bold text-slate-900">{m.payee}</span>
                    <span class="text-[10px] text-slate-400 block">{m.primary_category}</span>
                  </div>
                </div>
                <div class="text-right">
                  <div class="font-black text-slate-900">{formatCents(m.total_cents)}</div>
                  <div class="text-[10px] text-slate-500 font-semibold">{m.transaction_count} txns</div>
                </div>
              </div>
            {/each}
          </div>
        </div>
      {/if}
    </div>

    <!-- US-5.15 Recurring Subscriptions Tracker & US-5.16 Budget Variance -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <!-- US-5.15 Subscriptions Tracker -->
      {#if subscriptionsData}
        <div class="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-4 print:break-inside-avoid">
          <div class="flex items-center justify-between border-b pb-3">
            <div>
              <h3 class="text-base font-bold text-slate-900">Recurring Subscriptions & Bills</h3>
              <p class="text-[11px] text-slate-500">Detected regular recurring charges & predicted due dates</p>
            </div>
            <div class="text-right">
              <span class="text-xs font-black text-indigo-600">{formatCents(subscriptionsData.total_estimated_monthly_cents)}/mo</span>
            </div>
          </div>

          {#if subscriptionsData.subscriptions.length === 0}
            <div class="p-6 text-center text-slate-400 text-xs font-semibold">
              No recurring subscription charges detected yet.
            </div>
          {:else}
            <div class="space-y-2 text-xs">
              {#each subscriptionsData.subscriptions as sub}
                <div class="p-3 rounded-xl border border-slate-200 bg-slate-50/70 flex items-center justify-between">
                  <div class="space-y-0.5">
                    <div class="font-bold text-slate-900 flex items-center gap-2">
                      <span>{sub.payee}</span>
                      <span class="px-1.5 py-0.5 rounded text-[9px] font-extrabold bg-indigo-100 text-indigo-800">{sub.frequency}</span>
                    </div>
                    <div class="text-[10px] text-slate-500 font-semibold">
                      Category: {sub.category_name} &bull; Next Due: <span class="text-slate-800 font-bold">{sub.predicted_next_due_date}</span>
                    </div>
                  </div>
                  <div class="text-right">
                    <div class="font-black text-slate-900">{formatCents(sub.average_amount_cents)}</div>
                  </div>
                </div>
              {/each}
            </div>
          {/if}
        </div>
      {/if}

      <!-- US-5.16 Budget Variance Report -->
      {#if budgetVarianceData}
        <div class="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-4 print:break-inside-avoid">
          <div class="flex items-center justify-between border-b pb-3">
            <div>
              <h3 class="text-base font-bold text-slate-900">Budget Variance Report</h3>
              <p class="text-[11px] text-slate-500">Accuracy evaluation for month {budgetVarianceData.month}</p>
            </div>
            <span class={`text-xs font-black ${budgetVarianceData.net_variance_cents >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
              Net: {formatCents(budgetVarianceData.net_variance_cents)}
            </span>
          </div>

          <div class="space-y-3 text-xs">
            {#if budgetVarianceData.over_budget_categories.length > 0}
              <div class="space-y-1">
                <span class="text-[10px] font-extrabold uppercase text-rose-600 tracking-wider">Over Budget</span>
                {#each budgetVarianceData.over_budget_categories as item}
                  <div class="p-2 rounded-xl bg-rose-50 border border-rose-200 flex items-center justify-between">
                    <span class="font-bold text-rose-950">{item.category_name}</span>
                    <span class="font-black text-rose-700">+{formatCents(Math.abs(item.variance_cents))} over ({item.percentage_used}%)</span>
                  </div>
                {/each}
              </div>
            {/if}

            {#if budgetVarianceData.under_budget_categories.length > 0}
              <div class="space-y-1">
                <span class="text-[10px] font-extrabold uppercase text-emerald-600 tracking-wider">Under Budget / Surplus</span>
                {#each budgetVarianceData.under_budget_categories.slice(0, 4) as item}
                  <div class="p-2 rounded-xl bg-emerald-50 border border-emerald-200 flex items-center justify-between">
                    <span class="font-bold text-emerald-950">{item.category_name}</span>
                    <span class="font-black text-emerald-700">{formatCents(item.variance_cents)} remaining</span>
                  </div>
                {/each}
              </div>
            {/if}
          </div>
        </div>
      {/if}
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
                    <button
                      type="button"
                      onclick={() => openDrilldownModal(item.payee)}
                      class="truncate max-w-[240px] text-indigo-600 hover:underline text-left"
                      title="Click to view transaction drill-down list (US-5.10)"
                    >
                      {item.payee} 🔍
                    </button>
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

  <!-- US-5.10 Initiator Transaction Drill-Down Modal -->
  {#if showDrilldownModal}
    <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 no-print">
      <div class="w-full max-w-2xl rounded-2xl bg-white p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
        <div class="flex items-center justify-between border-b pb-3">
          <div>
            <h3 class="text-lg font-bold text-slate-900">Transactions: {drilldownPayee}</h3>
            <p class="text-xs text-slate-500">Drill-down view of transactions making up this statistic (US-5.10)</p>
          </div>
          <button
            type="button"
            onclick={() => (showDrilldownModal = false)}
            class="text-slate-400 hover:text-slate-600 text-2xl font-bold px-2"
          >
            &times;
          </button>
        </div>

        {#if loadingDrilldown}
          <div class="p-8 text-center text-slate-500 text-xs font-semibold">
            Loading drill-down transactions...
          </div>
        {:else if drilldownTransactions.length === 0}
          <div class="p-8 text-center text-slate-400 text-xs font-semibold">
            No individual transactions found.
          </div>
        {:else}
          <div class="overflow-x-auto">
            <table class="w-full text-left text-xs text-slate-700">
              <thead class="bg-slate-100 uppercase text-[10px] font-extrabold text-slate-500">
                <tr>
                  <th class="p-2.5">Date</th>
                  <th class="p-2.5">Account</th>
                  <th class="p-2.5">Payee</th>
                  <th class="p-2.5 text-right">Amount ($)</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-100">
                {#each drilldownTransactions as tx}
                  <tr class="hover:bg-slate-50">
                    <td class="p-2.5 font-mono">{tx.date}</td>
                    <td class="p-2.5 font-bold">{tx.account_name || 'Account'}</td>
                    <td class="p-2.5">{tx.raw_payee}</td>
                    <td class="p-2.5 text-right font-black text-slate-900">{formatCents(tx.amount_cents)}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}

        <div class="flex justify-end pt-2">
          <button
            type="button"
            onclick={() => (showDrilldownModal = false)}
            class="rounded-xl border border-slate-300 bg-white px-4 py-1.5 text-xs font-bold text-slate-700 hover:bg-slate-50"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  {/if}
</div>

