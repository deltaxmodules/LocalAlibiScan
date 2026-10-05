import { useEffect, useState } from 'react';

export default function App() {
  const [products, setProducts] = useState([]);

  useEffect(() => {
    fetch('/api/products').then((r) => r.json()).then(setProducts);
  }, []);

  return (
    <ul>
      {products.map((p) => (
        <li key={p.id}>{p.name}</li>
      ))}
    </ul>
  );
}
