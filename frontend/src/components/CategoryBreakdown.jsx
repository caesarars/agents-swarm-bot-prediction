import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts'

const COLORS = ['#22d3ee', '#10b981', '#ef4444', '#f59e0b', '#a78bfa', '#f472b6', '#94a3b8', '#84cc16', '#fb7185', '#38bdf8']

export default function CategoryBreakdown({ breakdown }) {
  if (!breakdown) return null

  const data = Object.entries(breakdown).map(([cat, votes]) => ({
    name: cat,
    value: (votes.UP || 0) + (votes.DOWN || 0),
    up: votes.UP || 0,
    down: votes.DOWN || 0,
    abstain: votes.ABSTAIN || 0,
  }))

  return (
    <div className="rounded-xl bg-card p-6 border border-slate-800">
      <div className="text-xs uppercase tracking-wider text-slate-400 mb-2">Vote distribution by category</div>
      <div style={{ width: '100%', height: 280 }}>
        <ResponsiveContainer>
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              innerRadius={50}
              outerRadius={90}
              paddingAngle={2}
            >
              {data.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{ background: '#0f172a', border: '1px solid #1e293b' }}
              formatter={(value, _name, p) => [
                `${value} votes (UP ${p.payload.up} / DOWN ${p.payload.down} / ABS ${p.payload.abstain})`,
                p.payload.name,
              ]}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
