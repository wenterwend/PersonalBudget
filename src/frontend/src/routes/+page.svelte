<script lang="ts">
  import { onMount } from 'svelte';
  import {
    getAccounts,
    getCategoryGroups,
    createCategoryGroup,
    createCategory,
    getTransactions,
    deleteTransaction,
    getRules,
    updateRule,
    deleteRule,
    applySingleRule,
    applyAllRules,
    confirmCategory,
    retrainMLModel,
    getBudgetGrid,
    type Account,
    type CategoryGroup,
    type Transaction,
    type Rule,
    type MonthlyBudgetGridResponse,
  } from '$lib/api';

  import AccountSelector from '$lib/components/ledger/AccountSelector.svelte';
  import AccountModal from '$lib/components/ledger/AccountModal.svelte';
  import TransactionModal from '$lib/components/ledger/TransactionModal.svelte';
  import LedgerTable from '$lib/components/ledger/LedgerTable.svelte';

  import ImportModal from '$lib/components/imports/ImportModal.svelte';
  import RuleList from '$lib/components/rules/RuleList.svelte';
  import RuleModal from '$lib/components/rules/RuleModal.svelte';

  import BudgetGrid from '$lib/components/budget/BudgetGrid.svelte';
  import SurplusTransferModal from '$lib/components/budget/SurplusTransferModal.svelte';
  import CategoryModal from '$lib/components/budget/CategoryModal.svelte';

  import QueryBuilder from '$lib/components/query/QueryBuilder.svelte';
  import ReportsDashboard from '$lib/components/reports/ReportsDashboard.svelte';

  let accounts: Account[] = $state([]);
  let categoryGroups: CategoryGroup[] = $state([]);
  let transactions: Transaction[] = $state([]);
  let rules: Rule[] = $state([]);

  let selectedAccountId: string | null = $state(null);
  let includeClosedAccounts = $state(false);
  let loadingTransactions = $state(false);
  let loadingRules = $state(false);

  // Tab View state (Milestones 1–5)
  let activeTab: 'ledger' | 'budget' | 'rules' | 'reports' | 'query' = $state('ledger');

  // Budget state (Milestone 4)
  let selectedMonth: string = $state(new Date().toISOString().slice(0, 7));
  let budgetGrid: MonthlyBudgetGridResponse | null = $state(null);
  let loadingBudget = $state(false);
  let showSurplusModal = $state(false);

  // Category Modal state
  let showCategoryModal = $state(false);
  let defaultCategoryGroupId = $state('');

  // Account Modal state
  let showAccountModal = $state(false);
  let accountToEdit: Account | null = $state(null);

  // Transaction Modal state
  let showTxModal = $state(false);
  let txToEdit: Transaction | null = $state(null);

  // Import Modal state
  let showImportModal = $state(false);

  // Rule Modal state
  let showRuleModal = $state(false);
  let ruleToEdit: Rule | null = $state(null);

  // Filters state
  let currentFilters = $state({
    search: '',
    startDate: '',
    endDate: '',
    cleared: '',
  });

  onMount(async () => {
    await loadInitialData();
  });

  async function loadInitialData() {
    try {
      accounts = await getAccounts(includeClosedAccounts);
      categoryGroups = await getCategoryGroups();

      // Seed default category groups if none exist
      if (categoryGroups.length === 0) {
        await seedDefaultCategories();
        categoryGroups = await getCategoryGroups();
      }

      await loadTransactions();
      await loadRulesData();
      await loadBudgetGridData();
    } catch (e) {
      console.error('Failed to load initial data:', e);
    }
  }

  async function seedDefaultCategories() {
    const defaultGroups = [
      { name: 'Income', isIncome: true, cats: ['Salary', 'Freelance', 'Investments'] },
      { name: 'Living Expenses', isIncome: false, cats: ['Groceries', 'Housing & Rent', 'Utilities', 'Transportation'] },
      { name: 'Lifestyle', isIncome: false, cats: ['Dining Out', 'Entertainment', 'Shopping', 'Travel'] },
    ];

    for (let i = 0; i < defaultGroups.length; i++) {
      const g = defaultGroups[i];
      const createdGroup = await createCategoryGroup(g.name, i);
      for (const catName of g.cats) {
        await createCategory(createdGroup.id, catName, g.isIncome);
      }
    }
  }

  async function loadTransactions() {
    loadingTransactions = true;
    try {
      transactions = await getTransactions({
        accountId: selectedAccountId || undefined,
        search: currentFilters.search || undefined,
        startDate: currentFilters.startDate || undefined,
        endDate: currentFilters.endDate || undefined,
        cleared: currentFilters.cleared !== '' ? currentFilters.cleared === 'true' : undefined,
      });
    } catch (e) {
      console.error('Failed to load transactions:', e);
    } finally {
      loadingTransactions = false;
    }
  }

  async function loadRulesData() {
    loadingRules = true;
    try {
      rules = await getRules();
    } catch (e) {
      console.error('Failed to load rules:', e);
    } finally {
      loadingRules = false;
    }
  }

  async function loadBudgetGridData(monthStr?: string) {
    if (monthStr) selectedMonth = monthStr;
    loadingBudget = true;
    try {
      budgetGrid = await getBudgetGrid(selectedMonth);
    } catch (e) {
      console.error('Failed to load budget grid:', e);
    } finally {
      loadingBudget = false;
    }
  }

  function handleAccountSelect(event: CustomEvent<string | null>) {
    selectedAccountId = event.detail;
    loadTransactions();
  }

  async function handleToggleIncludeClosed(event: CustomEvent<boolean>) {
    includeClosedAccounts = event.detail;
    accounts = await getAccounts(includeClosedAccounts);
  }

  function handleOpenCreateAccount() {
    accountToEdit = null;
    showAccountModal = true;
  }

  function handleOpenEditAccount(event: CustomEvent<Account>) {
    accountToEdit = event.detail;
    showAccountModal = true;
  }

  async function handleAccountSaved() {
    accounts = await getAccounts(includeClosedAccounts);
    await loadTransactions();
    await loadBudgetGridData();
  }

  let hasAccounts = $derived(accounts.length > 0);

  function handleOpenCreateTx() {
    if (!hasAccounts) return;
    txToEdit = null;
    showTxModal = true;
  }

  function handleOpenEditTx(event: CustomEvent<Transaction>) {
    txToEdit = event.detail;
    showTxModal = true;
  }

  async function handleDeleteTx(event: CustomEvent<Transaction>) {
    const tx = event.detail;
    if (confirm(`Are you sure you want to delete transaction "${tx.raw_payee}"?`)) {
      try {
        await deleteTransaction(tx.id);
        accounts = await getAccounts(includeClosedAccounts);
        await loadTransactions();
        await loadBudgetGridData();
      } catch (e: any) {
        alert(e.message || 'Failed to delete transaction.');
      }
    }
  }

  async function handleTxSaved() {
    accounts = await getAccounts(includeClosedAccounts);
    await loadTransactions();
    await loadBudgetGridData();
  }

  function handleFilterChange(event: CustomEvent<{ search: string; startDate: string; endDate: string; cleared: string }>) {
    currentFilters = event.detail;
    loadTransactions();
  }

  // One-Click ML Category Confirmation (US-3.4)
  async function handleConfirmCategory(event: CustomEvent<{ transaction: Transaction; categoryId?: string }>) {
    const { transaction, categoryId } = event.detail;
    try {
      await confirmCategory(transaction.id, categoryId);
      await loadTransactions();
      await loadBudgetGridData();
    } catch (e: any) {
      alert(e.message || 'Failed to confirm ML category.');
    }
  }

  // Import Handlers
  function handleOpenImport() {
    if (!hasAccounts) return;
    showImportModal = true;
  }

  async function handleImportComplete() {
    accounts = await getAccounts(includeClosedAccounts);
    await loadTransactions();
    await loadBudgetGridData();
  }

  // Rule Handlers
  function handleOpenCreateRule() {
    ruleToEdit = null;
    showRuleModal = true;
  }

  function handleOpenEditRule(event: CustomEvent<Rule>) {
    ruleToEdit = event.detail;
    showRuleModal = true;
  }

  async function handleToggleRuleActive(event: CustomEvent<Rule>) {
    const rule = event.detail;
    try {
      await updateRule(rule.id, { is_active: !rule.is_active });
      await loadRulesData();
    } catch (e: any) {
      alert(e.message || 'Failed to update rule.');
    }
  }

  async function handleDeleteRule(event: CustomEvent<Rule>) {
    const rule = event.detail;
    if (confirm(`Are you sure you want to delete rule for "${rule.match_value}"?`)) {
      try {
        await deleteRule(rule.id);
        await loadRulesData();
      } catch (e: any) {
        alert(e.message || 'Failed to delete rule.');
      }
    }
  }

  async function handleApplySingleRule(event: CustomEvent<Rule>) {
    const rule = event.detail;
    try {
      const res = await applySingleRule(rule.id);
      alert(`Rule applied successfully! ${res.updated_transactions_count} historical transactions updated.`);
      await loadTransactions();
      await loadBudgetGridData();
    } catch (e: any) {
      alert(e.message || 'Failed to apply rule.');
    }
  }

  async function handleApplyAllRules() {
    try {
      const res = await applyAllRules();
      alert(`Rules engine applied! ${res.updated_transactions_count} transactions standardized.`);
      await loadTransactions();
      await loadBudgetGridData();
    } catch (e: any) {
      alert(e.message || 'Failed to apply rules.');
    }
  }

  async function handleRuleSaved() {
    await loadRulesData();
    await loadTransactions();
    await loadBudgetGridData();
  }

  function handleOpenCategoryModal(event: CustomEvent<{ defaultGroupId?: string }>) {
    defaultCategoryGroupId = event.detail?.defaultGroupId || '';
    showCategoryModal = true;
  }

  async function handleCategorySaved() {
    categoryGroups = await getCategoryGroups();
    await loadBudgetGridData();
    await loadTransactions();
  }

  // Budget Handlers
  function handleMonthChange(event: CustomEvent<string>) {
    selectedMonth = event.detail;
    loadBudgetGridData(selectedMonth);
  }

  function handleBudgetRefresh() {
    loadBudgetGridData();
  }

  async function handleSurplusComplete(event: CustomEvent<{ transferred_cents: number; target_account_name: string; transferred_categories: string[] }>) {
    const res = event.detail;
    alert(`Surplus Transfer Complete! Transferred ${(res.transferred_cents / 100).toLocaleString('en-US', { style: 'currency', currency: 'USD' })} across ${res.transferred_categories.length} categories to account "${res.target_account_name}".`);
    accounts = await getAccounts(includeClosedAccounts);
    await loadBudgetGridData();
    await loadTransactions();
  }
</script>

<div class="space-y-6">
  <!-- Top Action Header (Hidden when printing) -->
  <div class="no-print flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
    <div>
      <h1 class="text-2xl font-extrabold text-slate-900 tracking-tight">Personal Finance System</h1>
      <p class="text-xs text-slate-500">
        Milestones 1–5 Complete &bull; Multi-Account Ledger, Statement Ingestion, Rules Engine, ML Categorization, Envelope Budgeting, Query Builder & Analytics
      </p>
    </div>

    <!-- Mode Tabs & Actions -->
    <div class="flex flex-wrap items-center gap-3">
      <div class="grid grid-cols-5 rounded-xl bg-slate-200/80 p-1 text-xs font-bold">
        <button
          type="button"
          onclick={() => (activeTab = 'ledger')}
          class={`px-3 py-1.5 rounded-lg transition ${
            activeTab === 'ledger' ? 'bg-white text-indigo-700 shadow-sm' : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          Ledger View
        </button>
        <button
          type="button"
          onclick={() => (activeTab = 'budget')}
          class={`px-3 py-1.5 rounded-lg transition ${
            activeTab === 'budget' ? 'bg-white text-indigo-700 shadow-sm' : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          Budgeting
        </button>
        <button
          type="button"
          onclick={() => (activeTab = 'rules')}
          class={`px-3 py-1.5 rounded-lg transition ${
            activeTab === 'rules' ? 'bg-white text-indigo-700 shadow-sm' : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          Rules ({rules.length})
        </button>
        <button
          type="button"
          onclick={() => (activeTab = 'reports')}
          class={`px-3 py-1.5 rounded-lg transition ${
            activeTab === 'reports' ? 'bg-white text-indigo-700 shadow-sm' : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          Reports & Trends
        </button>
        <button
          type="button"
          onclick={() => (activeTab = 'query')}
          class={`px-3 py-1.5 rounded-lg transition ${
            activeTab === 'query' ? 'bg-white text-indigo-700 shadow-sm' : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          Query Builder
        </button>
      </div>

      <button
        type="button"
        onclick={handleOpenImport}
        disabled={!hasAccounts}
        title={!hasAccounts ? "Please add an account before importing bank statements" : "Import Bank Statement"}
        class="inline-flex items-center gap-1.5 rounded-xl border border-slate-300 bg-white px-3.5 py-2 text-xs font-bold text-slate-700 shadow-sm hover:bg-slate-50 disabled:opacity-40 disabled:pointer-events-none transition"
      >
        <span>📁 Import Bank Statement</span>
      </button>

      <button
        type="button"
        onclick={handleOpenCreateTx}
        disabled={!hasAccounts}
        title={!hasAccounts ? "Please add an account before creating transactions" : "Add Transaction"}
        class="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-xs font-bold text-white shadow-md hover:bg-indigo-700 active:scale-95 disabled:opacity-40 disabled:pointer-events-none transition"
      >
        <span class="text-base leading-none">+</span> Add Transaction
      </button>
    </div>
  </div>

  {#if activeTab === 'ledger'}
    <!-- Account Selector Component (US-1.1, US-1.2) -->
    <AccountSelector
      {accounts}
      {selectedAccountId}
      includeClosed={includeClosedAccounts}
      on:select={handleAccountSelect}
      on:createAccount={handleOpenCreateAccount}
      on:editAccount={handleOpenEditAccount}
      on:toggleIncludeClosed={handleToggleIncludeClosed}
    />

    <!-- Ledger Transactions Table (US-1.2, US-1.3, US-1.4, US-3.4) -->
    <LedgerTable
      {transactions}
      showAccountColumn={selectedAccountId === null}
      loading={loadingTransactions}
      on:edit={handleOpenEditTx}
      on:delete={handleDeleteTx}
      on:confirmCategory={handleConfirmCategory}
      on:filterChange={handleFilterChange}
    />
  {:else if activeTab === 'budget'}
    <!-- Monthly Budget Grid View (US-4.1, US-4.2, US-4.3, US-4.4, US-4.5, US-4.6) -->
    <BudgetGrid
      month={selectedMonth}
      grid={budgetGrid}
      loading={loadingBudget}
      on:monthChange={handleMonthChange}
      on:refresh={handleBudgetRefresh}
      on:openSurplusModal={() => (showSurplusModal = true)}
      on:openCategoryModal={handleOpenCategoryModal}
    />
  {:else if activeTab === 'rules'}
    <!-- Rules Management List View (US-3.1, US-3.2) -->
    <RuleList
      {rules}
      loading={loadingRules}
      on:createRule={handleOpenCreateRule}
      on:editRule={handleOpenEditRule}
      on:deleteRule={handleDeleteRule}
      on:toggleActive={handleToggleRuleActive}
      on:applySingle={handleApplySingleRule}
      on:applyAll={handleApplyAllRules}
    />
  {:else if activeTab === 'reports'}
    <!-- Financial Trends & Reporting Analytics Dashboard (US-5.3, US-5.4) -->
    <ReportsDashboard />
  {:else if activeTab === 'query'}
    <!-- Custom Visual AST Query Builder & CSV Exporter (US-5.1, US-5.2) -->
    <QueryBuilder {accounts} {categoryGroups} />
  {/if}
</div>

<!-- Account CRUD Modal -->
<AccountModal
  show={showAccountModal}
  {accountToEdit}
  on:close={() => (showAccountModal = false)}
  on:save={handleAccountSaved}
/>

<!-- Quick Manual Entry & Split Transactions Modal (US-1.3, US-1.4) -->
<TransactionModal
  show={showTxModal}
  transactionToEdit={txToEdit}
  {accounts}
  {categoryGroups}
  defaultAccountId={selectedAccountId}
  on:close={() => (showTxModal = false)}
  on:save={handleTxSaved}
/>

<!-- File Statement Import & Column Mapper Modal (US-2.1, US-2.2, US-2.3) -->
<ImportModal
  show={showImportModal}
  {accounts}
  defaultAccountId={selectedAccountId}
  on:close={() => (showImportModal = false)}
  on:complete={handleImportComplete}
/>

<!-- Automation Rule Definition Modal (US-3.1, US-3.2) -->
<RuleModal
  show={showRuleModal}
  {ruleToEdit}
  {categoryGroups}
  on:close={() => (showRuleModal = false)}
  on:save={handleRuleSaved}
/>

<!-- Category Surplus Transfer to Savings Modal (US-4.5) -->
<SurplusTransferModal
  show={showSurplusModal}
  month={selectedMonth}
  grid={budgetGrid}
  {accounts}
  on:close={() => (showSurplusModal = false)}
  on:complete={handleSurplusComplete}
/>

<!-- Custom Budget Category / Category Group Modal (US-4.6) -->
<CategoryModal
  show={showCategoryModal}
  {categoryGroups}
  defaultGroupId={defaultCategoryGroupId}
  on:close={() => (showCategoryModal = false)}
  on:save={handleCategorySaved}
/>
