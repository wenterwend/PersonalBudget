<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { Account, CSVPreviewResponse, ImportSummary } from '$lib/api';
  import { uploadCSVPreview, processCSVImport, processQFXImport } from '$lib/api';

  let {
    show = false,
    accounts = [],
    defaultAccountId = null,
  }: {
    show?: boolean;
    accounts?: Account[];
    defaultAccountId?: string | null;
  } = $props();

  const dispatch = createEventDispatcher<{ complete: void; close: void }>();

  let currentStep: 'upload' | 'map' | 'summary' = $state('upload');
  let selectedFile: File | null = $state(null);
  let fileType: 'csv' | 'qfx' = $state('csv');
  let fileContentStr: string = $state('');

  let accountId = $state('');
  let skipDuplicates = $state(true);

  // CSV Preview data
  let headers: string[] = $state([]);
  let sampleRows: Record<string, string>[] = $state([]);

  // Mappings
  let dateCol = $state('');
  let payeeCol = $state('');
  let amountMode: 'single' | 'debit_credit' = $state('single');
  let amountCol = $state('');
  let debitCol = $state('');
  let creditCol = $state('');
  let notesCol = $state('');
  let dateFormat = $state('');

  let loading = $state(false);
  let error: string | null = $state(null);

  // Import Summary Output
  let summaryResult: ImportSummary | null = $state(null);

  $effect(() => {
    if (show) {
      currentStep = 'upload';
      selectedFile = null;
      fileContentStr = '';
      accountId = defaultAccountId || accounts[0]?.id || '';
      skipDuplicates = true;
      error = null;
      summaryResult = null;
    }
  });

  async function handleFileSelect(event: Event) {
    const input = event.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) return;
    const file = input.files[0];
    await processSelectedFile(file);
  }

  async function handleDrop(event: DragEvent) {
    event.preventDefault();
    if (!event.dataTransfer?.files || event.dataTransfer.files.length === 0) return;
    const file = event.dataTransfer.files[0];
    await processSelectedFile(file);
  }

  async function processSelectedFile(file: File) {
    selectedFile = file;
    loading = true;
    error = null;

    try {
      const ext = file.name.toLowerCase();
      if (ext.endsWith('.qfx') || ext.endsWith('.ofx')) {
        fileType = 'qfx';
        fileContentStr = await file.text();
        currentStep = 'map';
      } else {
        fileType = 'csv';
        fileContentStr = await file.text();
        const preview = await uploadCSVPreview(file);
        headers = preview.headers;
        sampleRows = preview.sample_rows;

        // Auto-detect columns
        autoDetectColumns(preview.headers);
        currentStep = 'map';
      }
    } catch (e: any) {
      error = e.message || 'Failed to read file.';
    } finally {
      loading = false;
    }
  }

  function autoDetectColumns(headList: string[]) {
    const lowerHeads = headList.map((h) => h.toLowerCase());

    const dateIdx = lowerHeads.findIndex((h) => h.includes('date') || h.includes('dt') || h.includes('posted'));
    if (dateIdx !== -1) dateCol = headList[dateIdx];

    const payeeIdx = lowerHeads.findIndex(
      (h) => h.includes('payee') || h.includes('description') || h.includes('name') || h.includes('vendor') || h.includes('memo')
    );
    if (payeeIdx !== -1) payeeCol = headList[payeeIdx];

    const amtIdx = lowerHeads.findIndex((h) => h.includes('amount') || h.includes('sum') || h.includes('total'));
    const debitIdx = lowerHeads.findIndex((h) => h.includes('debit') || h.includes('withdrawal') || h.includes('out'));
    const creditIdx = lowerHeads.findIndex((h) => h.includes('credit') || h.includes('deposit') || h.includes('in'));

    if (debitIdx !== -1 && creditIdx !== -1) {
      amountMode = 'debit_credit';
      debitCol = headList[debitIdx];
      creditCol = headList[creditIdx];
    } else if (amtIdx !== -1) {
      amountMode = 'single';
      amountCol = headList[amtIdx];
    } else if (headList.length >= 3) {
      amountCol = headList[2];
    }

    const notesIdx = lowerHeads.findIndex((h) => h.includes('note') || h.includes('comment') || h.includes('details'));
    if (notesIdx !== -1) notesCol = headList[notesIdx];
  }

  async function handleExecuteImport() {
    if (!accountId) {
      error = 'Please select a target account.';
      return;
    }
    if (fileType === 'csv' && (!dateCol || !payeeCol)) {
      error = 'Please map both Date and Payee columns.';
      return;
    }

    loading = true;
    error = null;

    try {
      if (fileType === 'qfx') {
        summaryResult = await processQFXImport({
          account_id: accountId,
          file_content: fileContentStr,
          skip_duplicates: skipDuplicates,
        });
      } else {
        summaryResult = await processCSVImport({
          account_id: accountId,
          file_content: fileContentStr,
          date_col: dateCol,
          payee_col: payeeCol,
          amount_col: amountMode === 'single' ? amountCol : undefined,
          debit_col: amountMode === 'debit_credit' ? debitCol : undefined,
          credit_col: amountMode === 'debit_credit' ? creditCol : undefined,
          notes_col: notesCol || undefined,
          date_format: dateFormat || undefined,
          skip_duplicates: skipDuplicates,
        });
      }
      currentStep = 'summary';
    } catch (e: any) {
      error = e.message || 'Import processing failed.';
    } finally {
      loading = false;
    }
  }

  function handleFinish() {
    dispatch('complete');
    dispatch('close');
  }

  function handleClose() {
    dispatch('close');
  }
</script>

{#if show}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 overflow-y-auto">
    <div class="w-full max-w-2xl rounded-xl bg-white p-6 shadow-2xl my-8">
      <div class="flex items-center justify-between pb-3 border-b">
        <h2 class="text-xl font-bold text-slate-800">
          {#if currentStep === 'upload'}
            Import Bank Statement
          {:else if currentStep === 'map'}
            Map Columns & Configure Import
          {:else}
            Import Results Summary
          {/if}
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

      <!-- STEP 1: UPLOAD FILE -->
      {#if currentStep === 'upload'}
        <div class="mt-6">
          <div
            role="region"
            aria-label="File Upload Dropzone"
            ondragover={(e) => e.preventDefault()}
            ondrop={handleDrop}
            class="flex flex-col items-center justify-center p-8 border-2 border-dashed border-slate-300 rounded-xl bg-slate-50 hover:bg-slate-100 transition cursor-pointer text-center"
          >
            <svg class="w-12 h-12 text-slate-400 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"/>
            </svg>
            <p class="text-sm font-semibold text-slate-700">Drag & drop your CSV or QFX/OFX file here</p>
            <p class="text-xs text-slate-500 mt-1">Supports bank exports (.csv, .qfx, .ofx)</p>

            <label class="mt-4 inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-xs font-bold text-white shadow-sm hover:bg-indigo-700 transition cursor-pointer">
              <span>Browse File</span>
              <input type="file" accept=".csv,.txt,.qfx,.ofx" onchange={handleFileSelect} class="hidden" />
            </label>
          </div>
        </div>
      {/if}

      <!-- STEP 2: COLUMN MAPPING (CSV / QFX) -->
      {#if currentStep === 'map'}
        <div class="mt-4 space-y-4">
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label for="import-account-select" class="block text-xs font-semibold text-slate-600 uppercase">Target Account</label>
              <select
                id="import-account-select"
                bind:value={accountId}
                required
                class="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm focus:ring-indigo-500"
              >
                <option value="" disabled>Select Target Account</option>
                {#each accounts as acc (acc.id)}
                  <option value={acc.id}>{acc.name} ({acc.type})</option>
                {/each}
              </select>
            </div>

            <div class="flex items-end">
              <label class="flex items-center text-xs font-medium text-slate-700 cursor-pointer select-none">
                <input
                  type="checkbox"
                  bind:checked={skipDuplicates}
                  class="mr-2 h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                />
                Skip duplicates (SHA-256 hash match)
              </label>
            </div>
          </div>

          {#if fileType === 'csv'}
            <div class="border-t border-slate-200 pt-4">
              <h3 class="text-sm font-bold text-slate-800 mb-3">Map CSV Columns</h3>
              
              <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label for="date-col-select" class="block text-xs font-medium text-slate-600">Date Column *</label>
                  <select
                    id="date-col-select"
                    bind:value={dateCol}
                    class="mt-1 block w-full rounded border border-slate-300 px-2.5 py-1.5 text-xs text-slate-900"
                  >
                    <option value="">-- Select Date Header --</option>
                    {#each headers as h}
                      <option value={h}>{h}</option>
                    {/each}
                  </select>
                </div>

                <div>
                  <label for="date-format-select" class="block text-xs font-medium text-slate-600">Date Format (Optional)</label>
                  <select
                    id="date-format-select"
                    bind:value={dateFormat}
                    class="mt-1 block w-full rounded border border-slate-300 px-2.5 py-1.5 text-xs text-slate-900"
                  >
                    <option value="">Auto-Detect Format</option>
                    <option value="%Y-%m-%d">YYYY-MM-DD (e.g. 2026-01-15)</option>
                    <option value="%m/%d/%Y">MM/DD/YYYY (e.g. 01/15/2026)</option>
                    <option value="%d/%m/%Y">DD/MM/YYYY (e.g. 15/01/2026)</option>
                  </select>
                </div>

                <div>
                  <label for="payee-col-select" class="block text-xs font-medium text-slate-600">Payee / Description Column *</label>
                  <select
                    id="payee-col-select"
                    bind:value={payeeCol}
                    class="mt-1 block w-full rounded border border-slate-300 px-2.5 py-1.5 text-xs text-slate-900"
                  >
                    <option value="">-- Select Payee Header --</option>
                    {#each headers as h}
                      <option value={h}>{h}</option>
                    {/each}
                  </select>
                </div>

                <div>
                  <label for="notes-col-select" class="block text-xs font-medium text-slate-600">Notes Column (Optional)</label>
                  <select
                    id="notes-col-select"
                    bind:value={notesCol}
                    class="mt-1 block w-full rounded border border-slate-300 px-2.5 py-1.5 text-xs text-slate-900"
                  >
                    <option value="">-- None --</option>
                    {#each headers as h}
                      <option value={h}>{h}</option>
                    {/each}
                  </select>
                </div>
              </div>

              <!-- Amount Mode Toggle -->
              <div class="mt-4 pt-3 border-t border-slate-100">
                <div class="flex items-center justify-between mb-2">
                  <span class="text-xs font-semibold text-slate-700">Amount Column Configuration</span>
                  <div class="grid grid-cols-2 rounded bg-slate-100 p-0.5 text-xs">
                    <button
                      type="button"
                      onclick={() => (amountMode = 'single')}
                      class={`px-2 py-0.5 rounded font-semibold transition ${
                        amountMode === 'single' ? 'bg-white text-indigo-700 shadow-sm' : 'text-slate-600'
                      }`}
                    >
                      Single Amount
                    </button>
                    <button
                      type="button"
                      onclick={() => (amountMode = 'debit_credit')}
                      class={`px-2 py-0.5 rounded font-semibold transition ${
                        amountMode === 'debit_credit' ? 'bg-white text-indigo-700 shadow-sm' : 'text-slate-600'
                      }`}
                    >
                      Debit & Credit
                    </button>
                  </div>
                </div>

                {#if amountMode === 'single'}
                  <div>
                    <label for="amount-col-select" class="block text-xs font-medium text-slate-600">Amount Column *</label>
                    <select
                      id="amount-col-select"
                      bind:value={amountCol}
                      class="mt-1 block w-full rounded border border-slate-300 px-2.5 py-1.5 text-xs text-slate-900"
                    >
                      <option value="">-- Select Amount Header --</option>
                      {#each headers as h}
                        <option value={h}>{h}</option>
                      {/each}
                    </select>
                  </div>
                {:else}
                  <div class="grid grid-cols-2 gap-4">
                    <div>
                      <label for="debit-col-select" class="block text-xs font-medium text-slate-600">Debit / Out Column</label>
                      <select
                        id="debit-col-select"
                        bind:value={debitCol}
                        class="mt-1 block w-full rounded border border-slate-300 px-2.5 py-1.5 text-xs text-slate-900"
                      >
                        <option value="">-- Select Debit Header --</option>
                        {#each headers as h}
                          <option value={h}>{h}</option>
                        {/each}
                      </select>
                    </div>

                    <div>
                      <label for="credit-col-select" class="block text-xs font-medium text-slate-600">Credit / In Column</label>
                      <select
                        id="credit-col-select"
                        bind:value={creditCol}
                        class="mt-1 block w-full rounded border border-slate-300 px-2.5 py-1.5 text-xs text-slate-900"
                      >
                        <option value="">-- Select Credit Header --</option>
                        {#each headers as h}
                          <option value={h}>{h}</option>
                        {/each}
                      </select>
                    </div>
                  </div>
                {/if}
              </div>

              <!-- Interactive Sample Data Preview -->
              {#if sampleRows.length > 0}
                <div class="mt-4 pt-3 border-t border-slate-100">
                  <h4 class="text-xs font-bold text-slate-700 mb-2">Sample File Rows Preview</h4>
                  <div class="overflow-x-auto rounded border border-slate-200">
                    <table class="w-full text-left text-[11px]">
                      <thead class="bg-slate-100 text-slate-600 border-b">
                        <tr>
                          {#each headers as h}
                            <th class={`py-1.5 px-2 font-semibold ${
                              h === dateCol || h === payeeCol || h === amountCol || h === debitCol || h === creditCol ? 'bg-indigo-100 text-indigo-900' : ''
                            }`}>{h}</th>
                          {/each}
                        </tr>
                      </thead>
                      <tbody class="divide-y divide-slate-100">
                        {#each sampleRows as row}
                          <tr>
                            {#each headers as h}
                              <td class="py-1.5 px-2 truncate max-w-[120px]">{row[h] || ''}</td>
                            {/each}
                          </tr>
                        {/each}
                      </tbody>
                    </table>
                  </div>
                </div>
              {/if}
            </div>
          {/if}

          <div class="flex justify-end space-x-3 pt-4 border-t">
            <button
              type="button"
              onclick={() => (currentStep = 'upload')}
              class="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              Back
            </button>
            <button
              type="button"
              onclick={handleExecuteImport}
              disabled={loading || !accountId}
              class="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
            >
              {loading ? 'Importing...' : 'Process Bank Import'}
            </button>
          </div>
        </div>
      {/if}

      <!-- STEP 3: SUMMARY RESULTS -->
      {#if currentStep === 'summary' && summaryResult}
        <div class="mt-6 text-center space-y-4">
          <div class="inline-flex items-center justify-center w-12 h-12 rounded-full bg-emerald-100 text-emerald-600 text-2xl font-bold mb-1">
            ✓
          </div>
          <h3 class="text-xl font-extrabold text-slate-900">Statement Ingestion Complete</h3>
          <p class="text-xs text-slate-500">Your bank transactions have been parsed, deduplicated, and passed through rules.</p>

          <div class="grid grid-cols-3 gap-3 pt-2">
            <div class="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-center">
              <div class="text-2xl font-black text-emerald-700">{summaryResult.inserted_count}</div>
              <div class="text-[11px] font-semibold text-emerald-800 uppercase">Inserted</div>
            </div>

            <div class="p-3 rounded-lg bg-amber-50 border border-amber-200 text-center">
              <div class="text-2xl font-black text-amber-700">{summaryResult.duplicate_count}</div>
              <div class="text-[11px] font-semibold text-amber-800 uppercase">Duplicates Skipped</div>
            </div>

            <div class="p-3 rounded-lg bg-indigo-50 border border-indigo-200 text-center">
              <div class="text-2xl font-black text-indigo-700">{summaryResult.rules_applied_count}</div>
              <div class="text-[11px] font-semibold text-indigo-800 uppercase">Rules Auto-Applied</div>
            </div>
          </div>

          <div class="pt-6 border-t flex justify-center">
            <button
              type="button"
              onclick={handleFinish}
              class="rounded-xl bg-indigo-600 px-6 py-2.5 text-sm font-bold text-white shadow-md hover:bg-indigo-700 transition"
            >
              Done & View Ledger
            </button>
          </div>
        </div>
      {/if}
    </div>
  </div>
{/if}
