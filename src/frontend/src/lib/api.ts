const API_BASE = 'http://localhost:8000/api';

export interface Account {
  id: string;
  name: string;
  type: 'checking' | 'savings' | 'credit' | 'investment';
  currency: string;
  opening_balance_cents: number;
  opening_date: string;
  is_closed: boolean;
  created_at: string;
  current_balance_cents: number;
  transaction_count: number;
}

export interface AccountCreate {
  name: string;
  type: 'checking' | 'savings' | 'credit' | 'investment';
  currency?: string;
  opening_balance_cents: number;
  opening_date: string;
  is_closed?: boolean;
}

export interface CategoryGroup {
  id: string;
  name: string;
  display_order: number;
  categories: Category[];
}

export interface Category {
  id: string;
  group_id: string;
  name: string;
  is_income: boolean;
  is_archived: boolean;
}

export interface SplitInput {
  category_id?: string | null;
  amount_cents: number;
  notes?: string | null;
}

export interface SplitResponse {
  id: string;
  transaction_id: string;
  category_id?: string | null;
  category_name?: string | null;
  amount_cents: number;
  notes?: string | null;
}

export interface Transaction {
  id: string;
  account_id: string;
  account_name?: string | null;
  date: string;
  raw_payee: string;
  normalized_payee?: string | null;
  amount_cents: number;
  notes?: string | null;
  cleared: boolean;
  import_hash?: string | null;
  is_ml_suggested: boolean;
  ml_confidence?: number | null;
  created_at: string;
  is_split: boolean;
  splits: SplitResponse[];
}

export interface TransactionCreate {
  account_id: string;
  date: string;
  raw_payee: string;
  normalized_payee?: string;
  amount_cents: number;
  notes?: string;
  cleared?: boolean;
  category_id?: string;
  splits?: SplitInput[];
}

export interface Rule {
  id: string;
  priority: number;
  match_field: 'raw_payee' | 'notes' | 'amount';
  match_type: 'contains' | 'exact' | 'starts_with';
  match_value: string;
  amount_condition: 'any' | 'income' | 'expense';
  secondary_match_field?: 'raw_payee' | 'notes' | 'amount' | null;
  secondary_match_type?: 'contains' | 'exact' | 'starts_with' | null;
  secondary_match_value?: string | null;
  target_payee?: string | null;
  target_category_id?: string | null;
  target_category_name?: string | null;
  is_active: boolean;
}

export interface RuleCreate {
  priority: number;
  match_field: 'raw_payee' | 'notes' | 'amount';
  match_type: 'contains' | 'exact' | 'starts_with';
  match_value: string;
  amount_condition?: 'any' | 'income' | 'expense';
  secondary_match_field?: 'raw_payee' | 'notes' | 'amount' | null;
  secondary_match_type?: 'contains' | 'exact' | 'starts_with' | null;
  secondary_match_value?: string | null;
  target_payee?: string;
  target_category_id?: string;
  is_active?: boolean;
}

export interface CSVPreviewResponse {
  headers: string[];
  sample_rows: Record<string, string>[];
}

export interface ImportSummary {
  inserted_count: number;
  duplicate_count: number;
  rules_applied_count: number;
}

export interface MLSuggestion {
  category_id: string;
  category_name: string;
  confidence: number;
}

export interface CategoryBudgetDetail {
  id: string;
  group_id: string;
  name: string;
  is_income: boolean;
  budgeted_cents: number;
  actual_cents: number;
  previous_rollover_cents: number;
  available_cents: number;
  carryover_enabled: boolean;
  rolling_3mo_avg_cents: number;
}

export interface CategoryGroupBudgetDetail {
  id: string;
  name: string;
  display_order: number;
  total_budgeted_cents: number;
  total_actual_cents: number;
  total_available_cents: number;
  categories: CategoryBudgetDetail[];
}

export interface MonthlyBudgetGridResponse {
  month: string;
  previous_month: string;
  next_month: string;
  total_income_cents: number;
  total_budgeted_cents: number;
  total_actual_cents: number;
  total_available_cents: number;
  groups: CategoryGroupBudgetDetail[];
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!res.ok) {
    let errorMsg = `HTTP Error ${res.status}`;
    try {
      const errJson = await res.json();
      if (errJson.detail) {
        errorMsg = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail);
      }
    } catch {}
    throw new Error(errorMsg);
  }

  if (res.status === 204) {
    return {} as T;
  }

  return res.json();
}

// Accounts API
export function getAccounts(includeClosed = false): Promise<Account[]> {
  return request<Account[]>(`/accounts?include_closed=${includeClosed}`);
}

export function createAccount(data: AccountCreate): Promise<Account> {
  return request<Account>('/accounts', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function updateAccount(id: string, data: Partial<AccountCreate>): Promise<Account> {
  return request<Account>(`/accounts/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export function deleteAccount(id: string): Promise<void> {
  return request<void>(`/accounts/${id}`, { method: 'DELETE' });
}

// Categories API
export function getCategoryGroups(includeArchived = false): Promise<CategoryGroup[]> {
  return request<CategoryGroup[]>(`/categories/groups?include_archived=${includeArchived}`);
}

export function createCategoryGroup(name: string, displayOrder = 0): Promise<CategoryGroup> {
  return request<CategoryGroup>('/categories/groups', {
    method: 'POST',
    body: JSON.stringify({ name, display_order: displayOrder }),
  });
}

export function createCategory(groupId: string, name: string, isIncome = false): Promise<Category> {
  return request<Category>('/categories', {
    method: 'POST',
    body: JSON.stringify({ group_id: groupId, name, is_income: isIncome }),
  });
}

export function deleteCategory(id: string): Promise<{ status: string; message: string }> {
  return request<{ status: string; message: string }>(`/categories/${id}`, { method: 'DELETE' });
}

export function deleteCategoryGroup(id: string): Promise<{ status: string; message: string }> {
  return request<{ status: string; message: string }>(`/categories/groups/${id}`, { method: 'DELETE' });
}

// Transactions API
export function getTransactions(filters: {
  accountId?: string;
  startDate?: string;
  endDate?: string;
  categoryId?: string;
  search?: string;
  cleared?: boolean;
} = {}): Promise<Transaction[]> {
  const params = new URLSearchParams();
  if (filters.accountId) params.append('account_id', filters.accountId);
  if (filters.startDate) params.append('start_date', filters.startDate);
  if (filters.endDate) params.append('end_date', filters.endDate);
  if (filters.categoryId) params.append('category_id', filters.categoryId);
  if (filters.search) params.append('search', filters.search);
  if (filters.cleared !== undefined) params.append('cleared', String(filters.cleared));

  const queryString = params.toString() ? `?${params.toString()}` : '';
  return request<Transaction[]>(`/transactions${queryString}`);
}

export function createTransaction(data: TransactionCreate): Promise<Transaction> {
  return request<Transaction>('/transactions', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function updateTransaction(id: string, data: Partial<TransactionCreate>): Promise<Transaction> {
  return request<Transaction>(`/transactions/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export function confirmCategory(transactionId: string, categoryId?: string, batch = false): Promise<Transaction> {
  const qs = batch ? '?batch=true' : '';
  return request<Transaction>(`/transactions/${transactionId}/confirm-category${qs}`, {
    method: 'POST',
    body: JSON.stringify({ category_id: categoryId }),
  });
}

export function getSuggestions(transactionId: string): Promise<{ suggestions: MLSuggestion[] }> {
  return request<{ suggestions: MLSuggestion[] }>(`/transactions/${transactionId}/suggestions`);
}

export function deleteTransaction(id: string): Promise<void> {
  return request<void>(`/transactions/${id}`, { method: 'DELETE' });
}

export interface SavedQuery {
  id: string;
  name: string;
  description?: string | null;
  query_ast: any;
  created_at: string;
  updated_at: string;
}

export function updateCategory(id: string, data: Partial<{ name: string; group_id: string; is_income: boolean; is_archived: boolean }>): Promise<Category> {
  return request<Category>(`/categories/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export function mergeCategory(sourceId: string, targetId: string): Promise<{ status: string; message: string }> {
  return request<{ status: string; message: string }>(`/categories/${sourceId}/merge`, {
    method: 'POST',
    body: JSON.stringify({ target_category_id: targetId }),
  });
}

export function getUncategorizedCount(): Promise<{ count: number }> {
  return request<{ count: number }>('/transactions/uncategorized-count');
}

// Rules API
export function getRules(filters: { search?: string; categoryId?: string; matchField?: string } = {}): Promise<Rule[]> {
  const params = new URLSearchParams();
  if (filters.search) params.append('q', filters.search);
  if (filters.categoryId) params.append('category_id', filters.categoryId);
  if (filters.matchField) params.append('match_field', filters.matchField);
  const qs = params.toString() ? `?${params.toString()}` : '';
  return request<Rule[]>(`/rules${qs}`);
}

export function previewRule(data: RuleCreate): Promise<{ match_count: number; sample_matches: any[] }> {
  return request<{ match_count: number; sample_matches: any[] }>('/rules/preview', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function createRule(data: RuleCreate, applyRetroactive = false): Promise<Rule> {
  return request<Rule>(`/rules?apply_retroactive=${applyRetroactive}`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function updateRule(id: string, data: Partial<RuleCreate>, applyRetroactive = false): Promise<Rule> {
  return request<Rule>(`/rules/${id}?apply_retroactive=${applyRetroactive}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export function deleteRule(id: string): Promise<void> {
  return request<void>(`/rules/${id}`, { method: 'DELETE' });
}

export function applySingleRule(id: string): Promise<{ updated_transactions_count: number }> {
  return request<{ updated_transactions_count: number }>(`/rules/${id}/apply`, { method: 'POST' });
}

export function applyAllRules(): Promise<{ updated_transactions_count: number }> {
  return request<{ updated_transactions_count: number }>('/rules/apply-all', { method: 'POST' });
}

// Saved Queries API
export function getSavedQueries(): Promise<SavedQuery[]> {
  return request<SavedQuery[]>('/queries/saved');
}

export function createSavedQuery(data: { name: string; description?: string; query_ast: any }): Promise<SavedQuery> {
  return request<SavedQuery>('/queries/saved', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function updateSavedQuery(id: string, data: { name?: string; description?: string; query_ast?: any }): Promise<SavedQuery> {
  return request<SavedQuery>(`/queries/saved/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export function deleteSavedQuery(id: string): Promise<void> {
  return request<void>(`/queries/saved/${id}`, { method: 'DELETE' });
}

export function executeSavedQuery(id: string): Promise<Transaction[]> {
  return request<Transaction[]>(`/queries/saved/${id}/execute`, { method: 'POST' });
}


// Machine Learning API
export function getMLStatus(): Promise<{ is_trained: boolean; classes_count: number }> {
  return request<{ is_trained: boolean; classes_count: number }>('/ml/status');
}

export function retrainMLModel(): Promise<{ status: string; is_trained: boolean; classes_count: number }> {
  return request<{ status: string; is_trained: boolean; classes_count: number }>('/ml/retrain', { method: 'POST' });
}

// Budgets API
export function getBudgetGrid(month: string): Promise<MonthlyBudgetGridResponse> {
  return request<MonthlyBudgetGridResponse>(`/budgets/grid?month=${month}`);
}

export function setBudget(payload: {
  month: string;
  category_id: string;
  budgeted_cents?: number;
  carryover_enabled?: boolean;
}): Promise<{ status: string }> {
  return request<{ status: string }>('/budgets/set', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function applyRollingAverages(month: string, monthsBack = 3): Promise<{ updated_count: number }> {
  return request<{ updated_count: number }>(`/budgets/apply-rolling-averages?month=${month}&months_back=${monthsBack}`, {
    method: 'POST',
  });
}

export function transferSurplusToSavings(payload: {
  month: string;
  category_ids: string[];
  target_account_id: string;
}): Promise<{ transferred_cents: number; target_account_name: string; transferred_categories: string[] }> {
  return request<{ transferred_cents: number; target_account_name: string; transferred_categories: string[] }>(
    '/budgets/transfer-surplus-to-savings',
    {
      method: 'POST',
      body: JSON.stringify(payload),
    }
  );
}

// Imports API
export async function uploadCSVPreview(file: File): Promise<CSVPreviewResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch(`${API_BASE}/imports/csv/preview`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    let errorMsg = `CSV Preview Error ${res.status}`;
    try {
      const errJson = await res.json();
      if (errJson.detail) errorMsg = errJson.detail;
    } catch {}
    throw new Error(errorMsg);
  }

  return res.json();
}

export function processCSVImport(payload: {
  account_id: string;
  file_content: string;
  date_col: string;
  payee_col: string;
  amount_col?: string;
  debit_col?: string;
  credit_col?: string;
  notes_col?: string;
  date_format?: string;
  skip_duplicates?: boolean;
}): Promise<ImportSummary> {
  return request<ImportSummary>('/imports/csv/process', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function processQFXImport(payload: {
  account_id: string;
  file_content: string;
  skip_duplicates?: boolean;
}): Promise<ImportSummary> {
  return request<ImportSummary>('/imports/qfx/process', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

// Reports & Query Builder API
export interface QueryRule {
  field: 'date' | 'amount_cents' | 'raw_payee' | 'normalized_payee' | 'account_id' | 'category_id' | 'cleared';
  operator: 'eq' | 'neq' | 'gt' | 'gte' | 'lt' | 'lte' | 'contains' | 'starts_with';
  value: any;
}

export interface QueryGroup {
  operator: 'AND' | 'OR';
  rules: (QueryRule | QueryGroup)[];
}

export interface QueryResult {
  count: number;
  total_amount_cents: number;
  transactions: Transaction[];
}

export interface CategorySpendingDetail {
  category_id: string;
  category_name: string;
  group_name: string;
  total_cents: number;
  percentage: number;
}

export interface SpendingByCategoryResponse {
  total_expense_cents: number;
  categories: CategorySpendingDetail[];
}

export interface MonthlyTrend {
  month: string;
  income_cents: number;
  expense_cents: number;
  net_savings_cents: number;
}

export interface IncomeVsExpenseResponse {
  months: MonthlyTrend[];
  total_income_cents: number;
  total_expense_cents: number;
  total_net_savings_cents: number;
}

export interface AccountSummary {
  id: string;
  name: string;
  type: string;
  current_balance_cents: number;
}

export interface NetWorthResponse {
  net_worth_cents: number;
  total_assets_cents: number;
  total_liabilities_cents: number;
  accounts: AccountSummary[];
}

export interface CategoryInitiatorDetail {
  payee: string;
  total_cents: number;
  transaction_count: number;
  percentage: number;
}

export interface CategoryInitiatorResponse {
  category_id: string;
  category_name: string;
  total_expense_cents: number;
  initiators: CategoryInitiatorDetail[];
}

export function runASTQuery(ast: QueryGroup): Promise<QueryResult> {
  return request<QueryResult>('/reports/query', {
    method: 'POST',
    body: JSON.stringify({ ast }),
  });
}

export async function downloadQueryCSV(ast: QueryGroup): Promise<void> {
  const res = await fetch(`${API_BASE}/reports/export-csv`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ast }),
  });

  if (!res.ok) {
    throw new Error(`CSV Export Error ${res.status}`);
  }

  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `transaction_export_${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

export function getSpendingByCategory(startDate?: string, endDate?: string): Promise<SpendingByCategoryResponse> {
  const params = new URLSearchParams();
  if (startDate) params.append('start_date', startDate);
  if (endDate) params.append('end_date', endDate);
  const qs = params.toString() ? `?${params.toString()}` : '';
  return request<SpendingByCategoryResponse>(`/reports/spending-by-category${qs}`);
}

export function getIncomeVsExpense(startDate?: string, endDate?: string): Promise<IncomeVsExpenseResponse> {
  const params = new URLSearchParams();
  if (startDate) params.append('start_date', startDate);
  if (endDate) params.append('end_date', endDate);
  const qs = params.toString() ? `?${params.toString()}` : '';
  return request<IncomeVsExpenseResponse>(`/reports/income-vs-expense${qs}`);
}

export function getNetWorthHistory(): Promise<NetWorthResponse> {
  return request<NetWorthResponse>('/reports/net-worth-history');
}

export function getCategoryInitiators(categoryId: string, startDate?: string, endDate?: string): Promise<CategoryInitiatorResponse> {
  const params = new URLSearchParams();
  params.append('category_id', categoryId);
  if (startDate) params.append('start_date', startDate);
  if (endDate) params.append('end_date', endDate);
  return request<CategoryInitiatorResponse>(`/reports/category-initiators?${params.toString()}`);
}

