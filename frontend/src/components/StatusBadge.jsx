export default function StatusBadge({ status }) {
  const map = {
    pending_review: 'bg-yellow-100 text-yellow-800',
    approved: 'bg-green-100 text-green-800',
    rejected: 'bg-red-100 text-red-800',
    processing: 'bg-blue-100 text-blue-800',
    completed: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
  }
  const label = {
    pending_review: 'Pending',
    approved: 'Approved',
    rejected: 'Rejected',
    processing: 'Processing',
    completed: 'Completed',
    failed: 'Failed',
  }
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${map[status] || 'bg-gray-100 text-gray-800'}`}>
      {label[status] || status}
    </span>
  )
}
