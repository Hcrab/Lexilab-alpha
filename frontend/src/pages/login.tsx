"use client"
import { useState, useContext } from 'react'
import { useRouter } from 'next/router'
import AuthContext from '../contexts/AuthContext'

export default function LoginPage() {
  const { login } = useContext(AuthContext)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const router = useRouter()

  const submit = async () => {
    const err = await login(username, password)
    if (err) {
      setError(err)
    } else {
      router.push('/')
    }
  }

  return (
    <main className="p-6 max-w-md mx-auto space-y-4">
      <h1 className="text-2xl font-bold">Login</h1>
      <input className="border p-2 w-full" placeholder="Username" value={username} onChange={e => setUsername(e.target.value)} />
      <input className="border p-2 w-full" type="password" placeholder="Password" value={password} onChange={e => setPassword(e.target.value)} />
      <button className="px-4 py-2 bg-blue-600 text-white" onClick={submit}>Login</button>
      {error && <p className="text-red-600">{error}</p>}
    </main>
  )
}
