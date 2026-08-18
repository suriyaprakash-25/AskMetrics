import { useEffect, useRef, useState } from 'react';
import { AlertCircle, Database, Loader2, Send } from 'lucide-react';
import { askQuestion, type AskResponse } from './api';
import { ChartRenderer } from './components/ChartRenderer';

interface Message {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  response?: AskResponse;
  isLoading?: boolean;
  error?: string;
}

function App() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      type: 'assistant',
      content: 'Ask a question about the commerce data. I will show the generated SQL and the returned result.',
    },
  ]);
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const question = input.trim();
    if (!question) return;

    const userMessage: Message = {
      id: `${Date.now()}-user`,
      type: 'user',
      content: question,
    };
    const assistantId = `${Date.now()}-assistant`;

    setMessages((previous) => [
      ...previous,
      userMessage,
      {
        id: assistantId,
        type: 'assistant',
        content: 'Analyzing your question…',
        isLoading: true,
      },
    ]);
    setInput('');

    try {
      const response = await askQuestion(question);
      const content = response.status === 'success'
        ? 'Here is what I found.'
        : response.status === 'refusal'
          ? 'I can’t answer that from the available data or safety policy.'
          : 'The query could not be completed safely.';

      setMessages((previous) => previous.map((message) =>
        message.id === assistantId
          ? { ...message, isLoading: false, content, response }
          : message,
      ));
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown backend error.';
      setMessages((previous) => previous.map((item) =>
        item.id === assistantId
          ? { ...item, isLoading: false, content: 'The backend request failed.', error: message }
          : item,
      ));
    }
  };

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand-icon"><Database size={24} /></div>
        <div>
          <h1>AskMetrics</h1>
          <p>Natural-language commerce analytics</p>
        </div>
      </header>

      <main className="conversation" aria-live="polite">
        {messages.map((message) => (
          <section
            key={message.id}
            className={`message-row ${message.type === 'user' ? 'user-row' : 'assistant-row'} animate-fade-in`}
          >
            <div className={`message-card ${message.type === 'user' ? 'user-card' : 'assistant-card'}`}>
              <div className="message-heading">
                {message.isLoading && <Loader2 size={18} className="animate-spin" />}
                {message.error && <AlertCircle size={18} className="error-icon" />}
                <span>{message.content}</span>
              </div>

              {message.error && <div className="error-text">{message.error}</div>}

              {message.response && (
                <div className="response-panel">
                  {message.response.status === 'success' && message.response.sql && (
                    <>
                      <div className="section-label">Generated SQL</div>
                      <pre className="sql-block"><code>{message.response.sql}</code></pre>
                    </>
                  )}

                  {message.response.status === 'success' && (
                    <>
                      <div className="section-label result-label">Result</div>
                      <ChartRenderer data={message.response.rows} />
                    </>
                  )}

                  {message.response.status === 'refusal' && (
                    <div className="state-box refusal-box">
                      <AlertCircle size={18} />
                      <div>
                        <strong>Refused</strong>
                        <p>{message.response.explanation}</p>
                      </div>
                    </div>
                  )}

                  {message.response.status === 'error' && (
                    <div className="state-box error-box">
                      <AlertCircle size={18} />
                      <div>
                        <strong>Query failed safely</strong>
                        <p>{message.response.explanation}</p>
                        {message.response.error && <small>{message.response.error}</small>}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </section>
        ))}
        <div ref={messagesEndRef} />
      </main>

      <footer className="composer-wrap">
        <form className="composer" onSubmit={handleSubmit}>
          <input
            type="text"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Ask a question about your data…"
            aria-label="Ask a question about your data"
            maxLength={2000}
          />
          <button type="submit" disabled={!input.trim()} aria-label="Send question">
            <Send size={20} />
          </button>
        </form>
      </footer>
    </div>
  );
}

export default App;
