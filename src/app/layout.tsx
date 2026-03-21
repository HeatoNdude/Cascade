import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Cascade',
  description: 'God View for your codebase',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body style={{ width: '100%', height: '100vh', overflow: 'hidden' }}>
        {children}
      </body>
    </html>
  )
}
