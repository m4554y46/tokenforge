'use client';

function fmt$(n: number): string {
  if (n >= 1000) return `$${(n / 1000).toFixed(1)}k`;
  if (n >= 1) return `$${n.toFixed(2)}`;
  return `${(n * 1000).toFixed(2)}¢`;
}

export function TrendChart({ data, height = 120 }: { data: { day: string; cost: number }[]; height?: number }) {
  if (!data.length) return <p className="text-xs text-gray-500">Aucune donnée de tendance</p>;

  const values = data.map(d => d.cost);
  const max = Math.max(...values, 0.001);
  const min = Math.min(...values, 0);
  const range = max - min || 1;
  const width = 100;
  const pts = data.map((d, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = ((d.cost - min) / range) * height;
    return `${x},${height - y}`;
  });
  const pathD = `M${pts.join(' L')}`;

  const firstVal = values[0];
  const lastVal = values[values.length - 1];
  const trendDir = lastVal > firstVal ? 'up' : lastVal < firstVal ? 'down' : 'flat';
  const trendPct = firstVal > 0 ? Math.round(((lastVal - firstVal) / firstVal) * 100) : 0;
  const trendColor = trendDir === 'up' ? 'text-red-400' : trendDir === 'down' ? 'text-green-400' : 'text-gray-400';
  const trendIcon = trendDir === 'up' ? '↑' : trendDir === 'down' ? '↓' : '→';

  return (
    <div>
      <div className="flex items-center gap-3 mb-1">
        <div className="flex items-center gap-4 text-xs">
          <span className="text-gray-400">Début: <strong className="text-gray-300">{fmt$(firstVal)}</strong></span>
          <span className="text-gray-500">→</span>
          <span className="text-gray-400">Fin: <strong className="text-gray-300">{fmt$(lastVal)}</strong></span>
          <span className={trendColor}>{trendIcon} {Math.abs(trendPct)}%</span>
        </div>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto" preserveAspectRatio="none">
        <defs>
          <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgb(251,146,60)" stopOpacity="0.2" />
            <stop offset="100%" stopColor="rgb(251,146,60)" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={`${pathD} L${width},${height} L0,${height} Z`} fill="url(#trendFill)" />
        <path d={pathD} fill="none" stroke="rgb(251,146,60)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        {data.filter((_, i) => i === 0 || i === data.length - 1).map((d, i) => {
          const idx = i === 0 ? 0 : data.length - 1;
          const x = (idx / (data.length - 1)) * width;
          const y = ((d.cost - min) / range) * height;
          return <circle key={i} cx={x} cy={height - y} r="2.5" fill="rgb(251,146,60)" />;
        })}
      </svg>
      <div className="flex justify-between text-xs text-gray-600 mt-0.5">
        <span>{data[0]?.day}</span>
        <span>{data[data.length - 1]?.day}</span>
      </div>
    </div>
  );
}