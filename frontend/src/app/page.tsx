export default function Home() {
  return (
    <main style={{ padding: '2rem', fontFamily: 'sans-serif' }}>
      <h1>Stock Intelligence</h1>
      <p>日本株AI予測・企業要約サービス</p>
      <p>
        API: <a href={`${process.env.NEXT_PUBLIC_API_URL}/docs`}>
          {process.env.NEXT_PUBLIC_API_URL}/docs
        </a>
      </p>
    </main>
  )
}
