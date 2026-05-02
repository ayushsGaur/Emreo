import { useEffect, useRef, useCallback, useState } from 'react'
import { createDashboardWS } from '../services/api'

let wsInstance = null
let socket = null
let isConnecting = false

export function useWebSocket(handlers) {
  const [status, setStatus] = useState('connecting')

  useEffect(() => {
    // 🚫 prevent multiple connects
    if (socket || isConnecting) return

    isConnecting = true

    socket = new WebSocket("ws://localhost:8000/api/v1/ws/dashboard")

    socket.onopen = () => {
      console.log("✅ WS Connected")
      setStatus("open")
      isConnecting = false
    }

    socket.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data)

        if (msg.event === "ping") {
          socket.send(JSON.stringify({ event: "pong" }))
          return
        }

        const handler = handlers[msg.event]
        if (handler) handler(msg.data)

      } catch {}
    }

    socket.onerror = () => {
      setStatus("error")
      isConnecting = false
    }

    socket.onclose = () => {
      console.log("WS closed")
      setStatus("closed")
      socket = null
      isConnecting = false
    }

  }, []) // 🔥 RUN ONLY ONCE

  return { status }

// export function useWebSocket(handlers) {
//   const wsRef      = useRef(null)
//   const retriesRef = useRef(0)
//   const timerRef   = useRef(null)
//   const hRef       = useRef(handlers)
//   const [status, setStatus] = useState('connecting')

//   useEffect(() => { hRef.current = handlers }, [handlers])

//   const ws = createDashboardWS()

// ws.onopen = () => {
//   console.log("✅ Dashboard WS Connected")
//   setStatus('open')
// }



// ws.onmessage = (e) => {
//   try {
//     const msg = JSON.parse(e.data)
//     const h = hRef.current[msg.event]
//     if (h) h(msg.data)

//     // respond to ping
//     if (msg.event === "ping") {
//       ws.send(JSON.stringify({ event: "pong" }))
//     }

//   } catch {}
// }

  // const connect = useCallback(() => {
  //   setStatus('connecting')
  //   const ws = createDashboardWS((msg) => {
  //     const h = hRef.current[msg.event]
  //     if (h) h(msg.data)
  //   })
  //   ws.onopen  = () => { setStatus('open'); retriesRef.current = 0 }
  //   ws.onclose = () => {
  //     setStatus('closed')
  //     if (retriesRef.current < 8) {
  //       timerRef.current = setTimeout(connect, 1000 * 2 ** retriesRef.current++)
  //     }
  //   }
  //   ws.onerror = () => setStatus('error')
  //   wsRef.current = ws
  // }, [])

  // useEffect(() => {
  //   connect()
  //   return () => { clearTimeout(timerRef.current); wsRef.current?.close() }
  // }, [connect])

// new fix down
//   const connect = useCallback(() => {
//   // ❗ CLOSE old connection first
//   if (wsRef.current) {
//     wsRef.current.close()
//   }

//   setStatus('connecting')

//   const ws = createDashboardWS()

//   ws.onopen = () => {
//     console.log("✅ Dashboard WS Connected")
//     setStatus('open')
//     retriesRef.current = 0
//   }

//   ws.onmessage = (e) => {
//     try {
//       const msg = JSON.parse(e.data)
//       const h = hRef.current[msg.event]
//       if (h) h(msg.data)

//       if (msg.event === "ping") {
//         ws.send(JSON.stringify({ event: "pong" }))
//       }
//     } catch {}
//   }

//   // ws.onclose = () => {
//   //   setStatus('closed')

//   //   if (retriesRef.current < 5) {
//   //     timerRef.current = setTimeout(connect, 2000)
//   //     retriesRef.current++
//   //   }
//   // }

//   ws.onclose = () => {
//   setStatus('closed')

//   if (retriesRef.current < 3) {
//     timerRef.current = setTimeout(() => {
//       retriesRef.current++
//       connect()
//     }, 2000)
//   }
// }

//   ws.onerror = () => setStatus('error')

//   wsRef.current = ws
// }, [])
const connect = useCallback(() => {
  // 🚫 If already connected, do nothing
  if (wsInstance && wsInstance.readyState === 1) {
    return
  }

  // 🔥 Close previous if exists
  if (wsInstance) {
    try { wsInstance.close() } catch {}
  }

  setStatus('connecting')

  const ws = createDashboardWS()

  ws.onopen = () => {
    console.log("✅ Dashboard WS Connected")
    setStatus('open')
    retriesRef.current = 0
  }

  ws.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data)

      const h = hRef.current[msg.event]
      if (h) h(msg.data)

      if (msg.event === "ping") {
        ws.send(JSON.stringify({ event: "pong" }))
      }
    } catch {}
  }

  ws.onclose = () => {
    setStatus('closed')

    if (retriesRef.current < 2) {
      retriesRef.current++
      setTimeout(connect, 2000)
    }
  }

  ws.onerror = () => {
    setStatus('error')
  }

  wsInstance = ws
  wsRef.current = ws
}, [])

useEffect(() => {
  // 🚫 Only connect ONCE globally
  if (wsInstance) return

  connect()

  return () => {
    clearTimeout(timerRef.current)

    // ❗ DO NOT CLOSE HERE (IMPORTANT)
    // wsRef.current?.close() ❌ REMOVE THIS LINE
  }
}, [])

//[connect] <- removed
 

// useEffect(() => {
//   if (wsRef.current) return  // ✅ stop duplicate connect

//   connect()

//   return () => {
//     clearTimeout(timerRef.current)

//     // ✅ close only if really open
//     if (wsRef.current && wsRef.current.readyState === 1) {
//       wsRef.current.close()
//     }
//   }
// }, [connect])

  return { status }
}
