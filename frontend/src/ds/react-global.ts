import * as React from 'react'

// AlignUI bundle.js klassik skript: React'ni window.React dan oladi.
// Bu modul bundle'dan oldin import qilinishi shart (ds/index.ts shunday qiladi).
;(window as unknown as { React: typeof React }).React = React
