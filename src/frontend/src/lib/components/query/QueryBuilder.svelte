<script lang="ts">
  import {
    runASTQuery,
    downloadQueryCSV,
    type QueryGroup,
    type QueryRule,
    type QueryResult,
    type Account,
    type CategoryGroup,
  } from '$lib/api';
  import { formatCents, dollarsToCents } from '$lib/utils/currency';

  let {
    accounts = [],
    categoryGroups = [],
  }: {
    accounts?: Account[];
    categoryGroups?: CategoryGroup[];
  } = $props();

  // Root AST State
  let ast: QueryGroup = $state({
    operator: 'AND',
    rules: [
      { field: 'amount_cents', operator: 'lt', value: 0 },
    ],
  });

  let queryResult: QueryResult | null = $state(null);
  let loading = $state(false);
  let exporting = $state(false);
  let error: string | null = $state(null);

  // Extract all categories from groups for category dropdown
  let allCategories = $derived.by(() => {
    const list: { id: string; name: string; groupName: string }[] = [];
    for (const group of categoryGroups) {
      for (const cat of group.categories) {
        list.push({ id: cat.id, name: cat.name, groupName: group.name });
      }
    }
    return list;
  });

  function addRule(group: QueryGroup) {
    group.rules = [
      ...group.rules,
      { field: 'raw_payee', operator: 'contains', value: '' },
    ];
  }

  function addSubgroup(group: QueryGroup) {
    group.rules = [
      ...group.rules,
      {
        operator: 'OR',
        rules: [{ field: 'raw_payee', operator: 'contains', value: '' }],
      },
    ];
  }

  function removeRule(parentGroup: QueryGroup, index: number) {
    parentGroup.rules = parentGroup.rules.filter((_, i) => i !== index);
  }

  async function handleRunQuery() {
    loading = true;
    error = null;
    try {
      // Process rule values before submitting (convert dollar inputs for amount_cents)
      const processedAST = prepareASTForSubmit(ast);
      queryResult = await runASTQuery(processedAST);
    } catch (e: any) {
      error = e.message || 'Failed to execute query.';
    } finally {
      loading = false;
    }
  }

  async function handleExportCSV() {
    exporting = true;
    error = null;
    try {
      const processedAST = prepareASTForSubmit(ast);
      await downloadQueryCSV(processedAST);
    } catch (e: any) {
      error = e.message || 'Failed to export CSV.';
    } finally {
      exporting = false;
    }
  }

  function prepareASTForSubmit(node: QueryGroup | QueryRule): any {
    if ('operator' in node && 'rules' in node) {
      return {
        operator: node.operator,
        rules: node.rules.map(prepareASTForSubmit),
      };
    } else {
      const rule = node as QueryRule;
      let val = rule.value;
      if (rule.field === 'amount_cents' && typeof val === 'number') {
        // If user entered dollars in UI, convert to cents
        val = Math.round(val * 100);
      }
      return {
        field: rule.field,
        operator: rule.operator,
        value: val,
      };
    }
  }
</script>

<div class="space-y-6">
  <!-- Top Header & Instructions -->
  <div class="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
    <div>
      <h2 class="text-xl font-extrabold text-slate-900 tracking-tight">Visual Query Builder</h2>
      <p class="text-xs text-slate-500 mt-1">
        Construct complex nested boolean AST rules (AND / OR) to slice financial transactions and export custom reports.
      </p>
    </div>

    <div class="flex items-center gap-3">
      <button
        type="button"
        onclick={handleRunQuery}
        disabled={loading}
        class="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-xs font-bold text-white shadow-md hover:bg-indigo-700 active:scale-95 transition"
      >
        <span>🔍 Run AST Query</span>
      </button>

      <button
        type="button"
        onclick={handleExportCSV}
        disabled={exporting}
        class="inline-flex items-center gap-1.5 rounded-xl border border-slate-300 bg-white px-3.5 py-2 text-xs font-bold text-slate-700 shadow-sm hover:bg-slate-50 transition"
      >
        <span>📥 Export CSV</span>
      </button>
    </div>
  </div>

  {#if error}
    <div class="p-4 rounded-xl bg-red-50 text-red-700 text-xs font-semibold border border-red-200">
      {error}
    </div>
  {/if}

  <!-- AST Rule Tree Editor -->
  <div class="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-4">
    <div class="flex items-center justify-between border-b pb-3">
      <div class="flex items-center gap-3">
        <span class="text-xs font-bold uppercase tracking-wider text-slate-500">Root Logical Match:</span>
        <select
          bind:value={ast.operator}
          class="rounded-xl border border-slate-300 bg-slate-50 px-3 py-1 text-xs font-black text-indigo-700 uppercase focus:outline-none focus:ring-1 focus:ring-indigo-500"
        >
          <option value="AND">Match ALL (AND)</option>
          <option value="OR">Match ANY (OR)</option>
        </select>
      </div>

      <div class="flex items-center gap-2">
        <button
          type="button"
          onclick={() => addRule(ast)}
          class="px-2.5 py-1 rounded-lg border border-slate-300 bg-white text-xs font-bold text-slate-700 hover:bg-slate-50 transition"
        >
          + Add Condition
        </button>
        <button
          type="button"
          onclick={() => addSubgroup(ast)}
          class="px-2.5 py-1 rounded-lg border border-slate-300 bg-white text-xs font-bold text-slate-700 hover:bg-slate-50 transition"
        >
          + Add Subgroup
        </button>
      </div>
    </div>

    <!-- Recursive Rule List Container -->
    <div class="space-y-3 pl-2 border-l-2 border-indigo-200">
      {#each ast.rules as item, idx}
        <div class="flex items-start gap-3 bg-slate-50/70 p-3 rounded-xl border border-slate-200">
          {#if 'operator' in item && 'rules' in item}
            <!-- Subgroup Node -->
            <div class="flex-1 space-y-3">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                  <span class="text-xs font-bold text-slate-500">SUBGROUP:</span>
                  <select
                    bind:value={item.operator}
                    class="rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs font-bold text-indigo-700 uppercase"
                  >
                    <option value="AND">Match ALL (AND)</option>
                    <option value="OR">Match ANY (OR)</option>
                  </select>
                </div>
                <div class="flex items-center gap-2">
                  <button
                    type="button"
                    onclick={() => addRule(item)}
                    class="px-2 py-0.5 rounded text-[11px] font-bold bg-white border text-slate-700"
                  >
                    + Condition
                  </button>
                  <button
                    type="button"
                    onclick={() => removeRule(ast, idx)}
                    class="text-rose-600 font-bold hover:underline text-xs"
                  >
                    Remove Group
                  </button>
                </div>
              </div>

              <!-- Nested Subgroup Rules -->
              <div class="space-y-2 pl-3 border-l-2 border-amber-300">
                {#each item.rules as subItem, subIdx}
                  {#if 'field' in subItem}
                    <div class="flex items-center gap-2">
                      <!-- Field -->
                      <select
                        bind:value={subItem.field}
                        class="rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs font-semibold text-slate-800"
                      >
                        <option value="date">Date</option>
                        <option value="raw_payee">Payee Name</option>
                        <option value="amount_cents">Amount ($)</option>
                        <option value="account_id">Account</option>
                        <option value="category_id">Category</option>
                        <option value="cleared">Cleared Status</option>
                      </select>

                      <!-- Operator -->
                      <select
                        bind:value={subItem.operator}
                        class="rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs font-semibold text-slate-800"
                      >
                        <option value="eq">equals</option>
                        <option value="neq">not equals</option>
                        <option value="contains">contains</option>
                        <option value="starts_with">starts with</option>
                        <option value="gt">greater than (&gt;)</option>
                        <option value="gte">greater or equal (&ge;)</option>
                        <option value="lt">less than (&lt;)</option>
                        <option value="lte">less or equal (&le;)</option>
                      </select>

                      <!-- Value Input -->
                      {#if subItem.field === 'account_id'}
                        <select
                          bind:value={subItem.value}
                          class="flex-1 rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs font-semibold text-slate-800"
                        >
                          {#each accounts as acc}
                            <option value={acc.id}>{acc.name}</option>
                          {/each}
                        </select>
                      {:else if subItem.field === 'category_id'}
                        <select
                          bind:value={subItem.value}
                          class="flex-1 rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs font-semibold text-slate-800"
                        >
                          {#each allCategories as cat}
                            <option value={cat.id}>{cat.groupName} &bull; {cat.name}</option>
                          {/each}
                        </select>
                      {:else if subItem.field === 'cleared'}
                        <select
                          bind:value={subItem.value}
                          class="flex-1 rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs font-semibold text-slate-800"
                        >
                          <option value={true}>Cleared (Yes)</option>
                          <option value={false}>Uncleared (No)</option>
                        </select>
                      {:else if subItem.field === 'date'}
                        <input
                          type="date"
                          bind:value={subItem.value}
                          class="flex-1 rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs font-semibold text-slate-800"
                        />
                      {:else if subItem.field === 'amount_cents'}
                        <input
                          type="number"
                          step="0.01"
                          placeholder="e.g. -50.00"
                          bind:value={subItem.value}
                          class="flex-1 rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs font-semibold text-slate-800"
                        />
                      {:else}
                        <input
                          type="text"
                          placeholder="Enter search text..."
                          bind:value={subItem.value}
                          class="flex-1 rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs font-semibold text-slate-800"
                        />
                      {/if}

                      <button
                        type="button"
                        onclick={() => removeRule(item, subIdx)}
                        class="text-slate-400 hover:text-rose-600 font-bold px-1 text-sm"
                      >
                        &times;
                      </button>
                    </div>
                  {/if}
                {/each}
              </div>
            </div>
          {:else}
            <!-- Rule Node -->
            <div class="flex-1 flex flex-wrap items-center gap-2">
              <span class="text-xs font-bold text-slate-400">WHERE</span>
              <select
                bind:value={item.field}
                class="rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs font-semibold text-slate-800"
              >
                <option value="date">Date</option>
                <option value="raw_payee">Payee Name</option>
                <option value="amount_cents">Amount ($)</option>
                <option value="account_id">Account</option>
                <option value="category_id">Category</option>
                <option value="cleared">Cleared Status</option>
              </select>

              <select
                bind:value={item.operator}
                class="rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs font-semibold text-slate-800"
              >
                <option value="eq">equals</option>
                <option value="neq">not equals</option>
                <option value="contains">contains</option>
                <option value="starts_with">starts with</option>
                <option value="gt">greater than (&gt;)</option>
                <option value="gte">greater or equal (&ge;)</option>
                <option value="lt">less than (&lt;)</option>
                <option value="lte">less or equal (&le;)</option>
              </select>

              {#if item.field === 'account_id'}
                <select
                  bind:value={item.value}
                  class="flex-1 min-w-[150px] rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs font-semibold text-slate-800"
                >
                  <option value="">Select Account</option>
                  {#each accounts as acc}
                    <option value={acc.id}>{acc.name}</option>
                  {/each}
                </select>
              {:else if item.field === 'category_id'}
                <select
                  bind:value={item.value}
                  class="flex-1 min-w-[150px] rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs font-semibold text-slate-800"
                >
                  <option value="">Select Category</option>
                  {#each allCategories as cat}
                    <option value={cat.id}>{cat.groupName} &bull; {cat.name}</option>
                  {/each}
                </select>
              {:else if item.field === 'cleared'}
                <select
                  bind:value={item.value}
                  class="flex-1 min-w-[150px] rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs font-semibold text-slate-800"
                >
                  <option value={true}>Cleared (Yes)</option>
                  <option value={false}>Uncleared (No)</option>
                </select>
              {:else if item.field === 'date'}
                <input
                  type="date"
                  bind:value={item.value}
                  class="flex-1 min-w-[140px] rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs font-semibold text-slate-800"
                />
              {:else if item.field === 'amount_cents'}
                <input
                  type="number"
                  step="0.01"
                  placeholder="e.g. -50.00"
                  bind:value={item.value}
                  class="flex-1 min-w-[140px] rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs font-semibold text-slate-800"
                />
              {:else}
                <input
                  type="text"
                  placeholder="Enter string..."
                  bind:value={item.value}
                  class="flex-1 min-w-[180px] rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs font-semibold text-slate-800"
                />
              {/if}

              <button
                type="button"
                onclick={() => removeRule(ast, idx)}
                class="text-slate-400 hover:text-rose-600 font-bold px-2 text-base"
                title="Remove Condition"
              >
                &times;
              </button>
            </div>
          {/if}
        </div>
      {/each}
    </div>
  </div>

  <!-- Query Execution Results -->
  {#if queryResult}
    <div class="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden space-y-4">
      <div class="p-4 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
        <div class="flex items-center gap-4 text-xs font-bold text-slate-700">
          <span>Found <strong class="text-indigo-600">{queryResult.count}</strong> matching transactions</span>
          <span>Net Total: <strong class={queryResult.total_amount_cents >= 0 ? 'text-emerald-600' : 'text-rose-600'}>
            {formatCents(queryResult.total_amount_cents)}
          </strong></span>
        </div>

        <button
          type="button"
          onclick={handleExportCSV}
          class="text-xs font-bold text-indigo-600 hover:underline"
        >
          Export CSV File
        </button>
      </div>

      {#if queryResult.transactions.length === 0}
        <div class="p-8 text-center text-slate-500 text-sm font-semibold">
          No transactions match the specified AST filter criteria.
        </div>
      {:else}
        <div class="overflow-x-auto">
          <table class="w-full text-left text-xs text-slate-700">
            <thead class="bg-slate-100 uppercase text-[10px] font-extrabold text-slate-500 tracking-wider border-b">
              <tr>
                <th scope="col" class="py-3 px-4">Date</th>
                <th scope="col" class="py-3 px-4">Account</th>
                <th scope="col" class="py-3 px-4">Payee</th>
                <th scope="col" class="py-3 px-4 text-right">Amount ($)</th>
                <th scope="col" class="py-3 px-4">Category</th>
                <th scope="col" class="py-3 px-4 text-center">Cleared</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-100">
              {#each queryResult.transactions as tx}
                <tr class="hover:bg-slate-50 transition">
                  <td class="py-2.5 px-4 font-mono font-semibold text-slate-600">{tx.date}</td>
                  <td class="py-2.5 px-4 font-bold text-slate-800">{tx.account_name || 'Account'}</td>
                  <td class="py-2.5 px-4 font-semibold text-slate-900">{tx.raw_payee}</td>
                  <td class={`py-2.5 px-4 text-right font-black ${tx.amount_cents >= 0 ? 'text-emerald-600' : 'text-slate-900'}`}>
                    {formatCents(tx.amount_cents)}
                  </td>
                  <td class="py-2.5 px-4 font-medium text-slate-600">
                    {#if tx.splits && tx.splits.length > 0}
                      {tx.splits.map((s) => s.category_name || 'Uncategorized').join(', ')}
                    {:else}
                      Uncategorized
                    {/if}
                  </td>
                  <td class="py-2.5 px-4 text-center">
                    {#if tx.cleared}
                      <span class="inline-block h-2.5 w-2.5 rounded-full bg-emerald-500" title="Cleared"></span>
                    {:else}
                      <span class="inline-block h-2.5 w-2.5 rounded-full bg-amber-400" title="Uncleared"></span>
                    {/if}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </div>
  {/if}
</div>
