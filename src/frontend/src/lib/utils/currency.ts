export function formatCents(cents: number, currency: string = 'USD'): string {
  const dollars = cents / 100;
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(dollars);
}

export function centsToDollars(cents: number): number {
  return cents / 100;
}

export function dollarsToCents(dollars: number | string): number {
  const val = typeof dollars === 'string' ? parseFloat(dollars) : dollars;
  if (isNaN(val)) return 0;
  return Math.round(val * 100);
}
