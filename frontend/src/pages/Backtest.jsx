import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { runBacktest } from '../api/backtest'
import BacktestForm from '../components/backtest/BacktestForm'
import BacktestResults from '../components/backtest/BacktestResults'

export default function Backtest() {
  const [result, setResult] = useState(null)

  const mutation = useMutation({
    mutationFn: runBacktest,
    onSuccess: setResult,
  })

  return (
    <div className="max-w-3xl space-y-6">
      <BacktestForm
        onSubmit={mutation.mutate}
        loading={mutation.isPending}
      />

      {mutation.isError && (
        <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded px-4 py-3">
          {mutation.error.message}
        </div>
      )}

      {result && <BacktestResults result={result} />}
    </div>
  )
}
