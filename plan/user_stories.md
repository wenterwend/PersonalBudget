# User Stories

## 1. Account & Ledger Management

### US-1.1: Multi-Account Management
As a user, I want to create, edit, archive, and view multiple financial accounts (checking, savings, credit cards) with an opening balance and date, so that I can track all my financial balances in one place.

### US-1.2: Unified vs. Account-Specific Views
As a user, I want to toggle between viewing a combined "All Accounts" ledger and filtering down to individual accounts, so that I can audit specific statements or get a consolidated view of my cash flow.

### US-1.3: Manual Transaction Entry
As a user (especially on mobile), I want to quickly enter a single transaction with date, account, payee, category, amount, and notes, so that I can record purchases immediately on the go.

### US-1.4: Split Transactions
As a user, I want to divide a single transaction into multiple categories and amounts, so that a single trip to a superstore (e.g., Target) accurately reflects spending across groceries, home goods, and clothing.

### US-1.5: Automated Database Backups & Safe Schema Change Scripts
As a user, I want automated backups on application startup and non-destructive schema change scripts, so that my historical database records are preserved across application updates, schema changes, and test executions.


## 2. Transaction Import & Parsing

### US-2.1: File-Based Transaction Import
As a user, I want to upload CSV and QFX/OFX export files from my bank, so that I don't have to manually enter dozens of transactions at once.

### US-2.2: Column Mapping Interface
As a user, I want an interactive column-mapper for CSV files (date format, payee, debit/credit or sign-based amount), so that I can import exports from different banks that use varying headers.

### US-2.3: Duplicate Detection
As a user, I want the importer to detect potential duplicate transactions (matching date, amount, and similar payee), so that overlapping statement downloads do not corrupt account balances.

## 3. Rules, Categorization & Learning Engine

### US-3.1: Explicit Rule Definition
As a user, I want to define rules with contains, starts_with, or exact match conditions on raw payee strings to set a standardized payee name and category automatically, so that raw bank text is cleaned consistently.

### US-3.2: Retroactive Rule Application
As a user, I want the option to apply a new rule to all existing historical transactions upon saving it, so that I don't have to clean past transactions by hand.

### US-3.3: Probabilistic Category Suggestions (Naive Bayes)
As a user, I want the system to suggest categories for un-ruled transactions based on my historical categorization habits, so that repetitive manual entry is minimized without writing exhaustive rules.

### US-3.4: One-Click Category Acceptance
As a user, I want transactions auto-categorized by machine learning to show a confidence indicator and allow one-click confirmation or quick correction in the UI, so that I maintain final authority over my ledger.

### US-3.5: Rules Search & Filtering
As a user, in the rules screen, I want to be able to search and filter the rules by payee, category, or match text so that they are easier to manage and review.

### US-3.6: Uncategorized Transaction Count
As a user, I want to see the total number of transactions that are uncategorized, so that I can easily determine how much I need to categorize.

### US-3.7: Rule Matching Preview & Count
As a user, when adding a rule, I want to see a preview and count of matches at the bottom of the modal window so that I can tell if the rule is effective before adding it.

### US-3.8: Batch Category Confirmation for Similar Transactions
As a user, when an imported transaction category is confirmed, update all similar transactions so that I don't have to click confirm on every transaction with the same base string.

## 4. Budgeting & Planning

### US-4.1: Category and Category Group Setup
As a user, I want to organize expense and income categories into custom groups (e.g., Housing, Transportation, Living Expenses), so that my budget is structurally organized.

### US-4.2: Multi-Month Average Spreading
As a user, I want to set a target budget amount calculated as an average of the last N months of actual spending, so that variable expenses (utilities, vehicle repairs) are budgeted realistically.

### US-4.3: Historical Month Navigation
As a user, I want to navigate backward and forward through prior and upcoming months, so that I can retroactively assign funds to older months or plan for the next month.

### US-4.4: Category Balance Rollover
As a user, I want the option to roll unspent funds or overspent balances forward into the next month's category balance, so that long-term sinking funds accumulate properly.

### US-4.5: Category Balance Transfer to Savings
As a user, I want the option to roll unspent funds from n categories forward into savings so that I can optimize savings.

### US-4.6: Category Creation, Customization & Removal
As a user, I want to add new expense or income categories and archive or remove unused budget categories, so that I can tailor the budget to my needs.

### US-4.7: Category Editing, Re-parenting & Merging
As a user, I want to be able to edit a budget sub category name or change it's parent category or merge an existing category into another, so that I can change my budget strategy.

### US-4.8: Positive Value Normalization for Rolling Average Budget Copies
As a user, on the budget screen, when I click copy for the 3 month average and the amount populates into the budget, ensure the amount is a positive value rather than retaining the negative amount so that I don't have to do that step manually.

### US-4.9: Annual or Quarterly Budget Value Application
As a user, on the budget screen, I want to be able to apply a budget value for a full year or quarter if I choose to, so that I can easily populate monthly budgets across multiple months without entering each month manually.


## 5. Query Builder, Reporting & Export

### US-5.1: Custom Visual Query Builder
As a user, I want to construct custom filter trees using nested AND/OR conditions across transaction fields (date range, category, payee, amount range, account), so that I can query specific spending trends.

### US-5.2: Query Result CSV Export
As a user, I want to export the current view or query result set directly to a CSV file, so that I can perform external analysis or share data.

### US-5.3: Spending Reports & Dashboards
As a user, I want to view interactive charts (spending by category over time, income vs. expenses, net worth trajectory), so that I can understand my financial trends at a glance.

### US-5.4: Printer-Friendly Reporting
As a user, I want a clean, dedicated print layout for monthly budget summaries and spending reports, so that I can print hard copies or save formatted PDFs without UI chrome.

### US-5.5: Saved Queries
As a user, I want to save queries with a saved name in the query builder so that I can easily access frequently used queries without rebuilding them.

### US-5.6: Uncategorized Option in Query Builder
As a user, I want to be able to select "Uncategorized" as an option in the Query Builder so that I can see which items are uncategorized.

### US-5.7: Category Breakdown by Transaction Initiator
As a user, on the reports screen, I want to be able to click on a category and see a chart or graph displaying a breakdown of the category by the transaction initiator so that I can understand the proportions of category attribution.

### US-5.8: Custom Date Range Selector in Reports
As a user, on the report screen, I want to be able to select a date range in addition to the period selector so that I can view trends like first quarter, second quarter.

### US-5.9: Context-Aware Query Input Validation & Field Operators
As a user, on the query builder page, I want to have rules on the query inputs such as not allowing letters when searching the amount field, and limiting operator selection based on the chosen field (e.g., preventing operators like greater-than when "account" is selected with an account dropdown picker), so that constructing queries is seamless without encountering errors.

### US-5.10: Initiator Transaction Drill-Down View in Reports
As a user, in the initiator breakdown view of a category, I want to click on a Payee and see a list of transactions that represent that group of transactions so that I can understand what made up that statistic.

### US-5.11: Month-over-Month Category Comparison Chart
As a user, on the reports screen, I want to view a month-over-month category comparison chart so that I can see spending trends and seasonal variations across categories over time.

### US-5.12: Fixed vs. Variable Expense Breakdown Report
As a user, on the reports screen, I want to view a fixed vs. variable expense breakdown so that I can distinguish mandatory living costs from discretionary spending.

### US-5.13: Day-of-Week & Monthly Heatmap Visualization
As a user, on the reports screen, I want to view a calendar heatmap of transaction spending by day of the week and date of the month so that I can identify peak spending habits.

### US-5.14: Top Merchant & Payee Leaderboard
As a user, on the reports screen, I want to view a top merchant/payee leaderboard ranking merchants by total spending amount and transaction frequency so that I can understand where most of my money goes.

### US-5.15: Recurring Subscriptions & Regular Bills Tracker
As a user, I want a dedicated subscriptions and recurring bills report that detects regular charges and predicts upcoming due dates so that I can track annual subscription overhead.

### US-5.16: Budget Variance (Over/Under Target) Report
As a user, on the budget and reports screens, I want a budget variance report highlighting over-budget and under-budget categories so that I can quickly evaluate budget accuracy.

### US-5.17: Savings Rate & Liquid Runway Trend Chart
As a user, on the reports screen, I want to view my net savings rate percentage and estimated liquid financial runway so that I can gauge my emergency financial security.






## 6. Multi-Device Access & Synchronization

### US-6.1: Mobile Progressive Web App (PWA)
As a mobile user, I want to install the web interface to my phone's home screen and experience a responsive, touch-friendly UI, so that checking balances and logging expenses feels like using a native mobile app.

### US-6.2: Concurrent Multi-User Access
As a family member, I want to view and edit transactions simultaneously with another user on the same central database without race conditions or locked database errors, so that shared household finances remain synchronized.

