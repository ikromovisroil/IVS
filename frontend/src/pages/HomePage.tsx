import { useAuth } from "../auth/AuthContext";

export default function HomePage() {
  const { me } = useAuth();

  return (
    <div>
      <h1>Xush kelibsiz{me?.employee ? `, ${me.employee.full_name}` : ""}</h1>
      <p>Chap tomondagi menyudan kerakli bo'limni tanlang.</p>
    </div>
  );
}
