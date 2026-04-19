import { useState } from 'react'

function App() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')

  const sendMessage = () => {
    if (!input.trim()) return
    setMessages([...messages, { role: 'user', text: input }])
    setInput('')
    setTimeout(() => {
      setMessages(prev => [...prev, { role: 'bot', text: 'RAG功能开发中...' }])
    }, 1000)
  }

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: '#fff' }}>
      <div style={{ flex: 2 }} />
      <div style={{ width: '33.33%', padding: '20px', borderLeft: '1px solid #ccc', background: '#fff' }}>
        <h2>RAG 对话</h2>
        <div style={{ height: '420px', border: '1px solid #ccc', overflow: 'auto', padding: '10px', marginBottom: '10px', background: '#fff' }}>
          {messages.length === 0 && <p style={{ color: '#999' }}>开始提问吧...</p>}
          {messages.map((msg, i) => (
            <div key={i} style={{ marginBottom: '8px', padding: '8px', background: msg.role === 'user' ? '#e3f2fd' : '#f5f5f5' }}>
              <strong>{msg.role === 'user' ? '我' : 'AI'}:</strong> {msg.text}
            </div>
          ))}
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <input
            style={{ flex: 1, padding: '8px', border: '1px solid #ccc' }}
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="问点什么..."
            onKeyDown={e => e.key === 'Enter' && sendMessage()}
          />
          <button style={{ padding: '8px 16px' }} onClick={sendMessage}>发送</button>
        </div>
      </div>
    </div>
  )
}

export default App
