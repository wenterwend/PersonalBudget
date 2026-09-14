<script lang="ts">
  import '../app.css';
  let { children } = $props();
</script>

<div class="min-h-screen flex flex-col bg-slate-50 text-slate-900 font-sans">
  <!-- Top Header Banner -->
  <header class="no-print bg-slate-900 text-white shadow-md">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex items-center justify-between h-16">
        <div class="flex items-center gap-3">
          <div class="bg-indigo-600 p-2 rounded-lg text-white font-bold text-lg leading-none">
            $
          </div>
          <div>
            <h1 class="text-lg font-bold tracking-tight">Personal Budget & Ledger</h1>
            <p class="text-[11px] text-slate-400">Multi-Account Household Finance System</p>
          </div>
        </div>
      </div>
    </div>
  </header>

  <!-- Main Content Body -->
  <main class="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
    {@render children()}
  </main>

  <footer class="no-print bg-white border-t border-slate-200 py-4 text-center text-xs text-slate-400">
    Personal Finance & Budgeting Application &bull; SQLite WAL Storage
  </footer>
</div>
