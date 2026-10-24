import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Stock Intelligence',
  description: '日本株AI予測・企業要約サービス',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="ja">
      <body>{children}</body>
    </html>
  )
}
