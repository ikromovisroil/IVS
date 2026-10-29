/** "20.10.2026 14:05" → ikki qator: sana, ostida (xira) vaqt. Jadvalda joy tejaydi. */
export default function DateTimeStack({ text }: { text: string }) {
  const i = text.lastIndexOf(' ')
  if (i < 0) return <>{text}</>
  return (
    <span style={{ display: 'inline-block', lineHeight: '20px' }}>
      {text.slice(0, i)}
      <br />
      <span style={{ color: 'var(--text-sub-600)' }}>{text.slice(i + 1)}</span>
    </span>
  )
}
