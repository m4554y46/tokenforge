export function KpiCard({
  label, value, subtitle, color, trend, progress
}: {
  label: string;
  value: string;
  subtitle?: string;
  color?: 'orange' | 'green' | 'red' | 'blue' | 'white' | 'yellow';
  trend?: { direction: 'up' | 'down' | 'flat'; label: string };
  progress?: { current: number; max: number };
}) {
  const colorMap: Record<string, string> = {
    orange: 'text-orange-400',
    green: 'text-green-400',
    red: 'text-red-400',
    blue: 'text-blue-400',
    white: 'text-white',
    yellow: 'text-yellow-400',
  };
  const textColor = colorMap[color ?? 'orange'];
  const trendIcon = trend?.direction === 'up' ? '↑' : trend?.direction === 'down' ? '↓' : '→';
  const trendColor = trend?.direction === 'up' ? 'text-green-400' : trend?.direction === 'down' ? 'text-red-400' : 'text-gray-400';
  const pct = progress ? Math.min((progress.current / progress.max) * 100, 100) : 0;
  const barColor = !progress ? '' : pct > 90 ? 'bg-red-500' : pct > 70 ? 'bg-yellow-500' : 'bg-green-500';

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-400">{label}</p>
        {trend && (
          <span className={`text-xs ${trendColor}`} title={trend.label}>
            {trendIcon} {trend.label}
          </span>
        )}
      </div>
      <p className={`text-2xl font-bold ${textColor} mt-1`}>{value}</p>
      {subtitle && <p className="text-xs text-gray-500 mt-1">{subtitle}</p>}
      {progress && (
        <div className="mt-2">
          <div className="w-full bg-gray-800 h-1.5 rounded-full overflow-hidden">
            <div className={`h-full rounded-full ${barColor}`} style={{ width: `${pct}%` }} />
          </div>
          <p className="text-xs text-gray-500 mt-0.5">{progress.current} / {progress.max}</p>
        </div>
      )}
    </div>
  );
}
