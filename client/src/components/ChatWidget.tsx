import { useState, useRef, useEffect } from 'react'
import { MessageSquare, X, Send, Loader2, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
}

interface ChatWidgetProps {
  fieldContext?: {
    name: string
    type: string
    description?: string
    tier?: string
  } | null
  onClose?: () => void
}

export function ChatWidget({ fieldContext, onClose }: ChatWidgetProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [currentContext, setCurrentContext] = useState<ChatWidgetProps['fieldContext']>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (fieldContext) {
      setIsOpen(true)
      setCurrentContext(fieldContext)
      const welcomeMessage: Message = {
        id: Date.now().toString(),
        role: 'assistant',
        content: `I'm here to help you understand the **${fieldContext.name}** field in the Stripe API. This is a ${fieldContext.type} field${fieldContext.tier ? ` available in the ${fieldContext.tier} tier` : ''}.\n\n${fieldContext.description || ''}\n\nWhat would you like to know about this field?`,
        timestamp: new Date(),
      }
      setMessages([welcomeMessage])
    }
  }, [fieldContext])

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  const openChatWithoutContext = () => {
    setIsOpen(true)
    setCurrentContext(null)
    const welcomeMessage: Message = {
      id: Date.now().toString(),
      role: 'assistant',
      content: `Hello! I'm your Stripe API Assistant - a Senior Payments Expert ready to help you understand:\n\n- **API fields and objects** - What each field does and when to use it\n- **Payment concepts** - Authorization holds, capture methods, payment intents, etc.\n- **Integration patterns** - Best practices for working with Stripe\n- **Business use cases** - How to use features for subscriptions, e-commerce, and more\n\nWhat would you like to know about Stripe's API?`,
      timestamp: new Date(),
    }
    setMessages([welcomeMessage])
  }

  const handleSend = async () => {
    if (!input.trim() || isLoading) return

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date(),
    }

    setMessages(prev => [...prev, userMessage])
    const userInput = input
    setInput('')
    setIsLoading(true)

    try {
      const contextToSend = currentContext || { name: 'General', type: 'general', description: 'General Stripe API question' }
      const historyToSend = messages.slice(-6).map(m => ({
        role: m.role,
        content: m.content
      }))
      
      const response = await api.askAI(userInput, {
        field: contextToSend,
        conversationHistory: historyToSend
      })

      if (response && response.answer) {
        const assistantMessage: Message = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: response.answer,
          timestamp: new Date(),
        }
        setMessages(prev => [...prev, assistantMessage])
      } else {
        throw new Error('No answer received')
      }
    } catch (error) {
      console.error('AI request failed:', error)
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        timestamp: new Date(),
      }
      setMessages(prev => [...prev, errorMessage])
    }
    setIsLoading(false)
  }

  const handleClose = () => {
    setIsOpen(false)
    setMessages([])
    setCurrentContext(null)
    onClose?.()
  }

  if (!isOpen) {
    return (
      <button
        onClick={openChatWithoutContext}
        className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br from-primary to-purple-600 text-white shadow-lg transition-all hover:scale-105 hover:shadow-xl pulse-ring"
      >
        <MessageSquare className="h-6 w-6" />
      </button>
    )
  }

  return (
    <div className="fixed bottom-6 right-6 z-50 flex h-[500px] w-[380px] flex-col overflow-hidden rounded-2xl border bg-card shadow-2xl chat-widget">
      <div className="flex items-center justify-between bg-gradient-to-r from-primary to-purple-600 px-4 py-3 text-white">
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5" />
          <div>
            <h3 className="font-semibold">AI Assistant</h3>
            <p className="text-xs opacity-90">
              {currentContext ? `Discussing: ${currentContext.name}` : 'Stripe API Expert'}
            </p>
          </div>
        </div>
        <Button variant="ghost" size="icon" onClick={handleClose} className="text-white hover:bg-white/20">
          <X className="h-5 w-5" />
        </Button>
      </div>

      <ScrollArea className="flex-1 p-4" ref={scrollRef}>
        <div className="space-y-4">
          {messages.map((message) => (
            <div
              key={message.id}
              className={cn(
                "flex",
                message.role === 'user' ? 'justify-end' : 'justify-start'
              )}
            >
              <div
                className={cn(
                  "max-w-[85%] rounded-2xl px-4 py-2.5 text-sm",
                  message.role === 'user'
                    ? 'bg-primary text-white rounded-br-md'
                    : 'bg-muted text-foreground rounded-bl-md'
                )}
              >
                <p className="whitespace-pre-wrap">{message.content}</p>
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="flex justify-start">
              <div className="flex items-center gap-2 rounded-2xl bg-muted px-4 py-3">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span className="text-sm text-muted-foreground">Thinking...</span>
              </div>
            </div>
          )}
        </div>
      </ScrollArea>

      <div className="border-t p-3">
        <form
          onSubmit={(e) => {
            e.preventDefault()
            handleSend()
          }}
          className="flex gap-2"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={currentContext ? `Ask about ${currentContext.name}...` : 'Ask about Stripe API...'}
            className="flex-1 rounded-full border bg-background px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/50"
          />
          <Button
            type="submit"
            size="icon"
            disabled={!input.trim() || isLoading}
            className="rounded-full"
          >
            <Send className="h-4 w-4" />
          </Button>
        </form>
      </div>
    </div>
  )
}
