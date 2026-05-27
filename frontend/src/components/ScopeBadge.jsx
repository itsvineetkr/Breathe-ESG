export default function ScopeBadge({ scope }) {
  const map = {
    scope_1: 'bg-orange-100 text-orange-800',
    scope_2: 'bg-blue-100 text-blue-800',
    scope_3: 'bg-purple-100 text-purple-800',
    '': 'bg-gray-100 text-gray-600',
  }
  const label = {
    scope_1: 'Scope 1',
    scope_2: 'Scope 2',
    scope_3: 'Scope 3',
    '': 'Unclassified',
  }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${map[scope] || 'bg-gray-100 text-gray-600'}`}>
      {label[scope] || scope}
    </span>
  )
}
