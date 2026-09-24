import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import LoginPage from "./auth/LoginPage";
import AppLayout from "./layout/AppLayout";
import HomePage from "./pages/HomePage";
import MaterialsPage from "./pages/MaterialsPage";
import TexnikaPage from "./pages/TexnikaPage";
import ArizalarPage from "./pages/ArizalarPage";
import AktPage from "./pages/AktPage";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<AppLayout />}>
            <Route index element={<HomePage />} />
            <Route path="materiallar" element={<MaterialsPage />} />
            <Route path="texnikalar" element={<TexnikaPage />} />
            <Route path="arizalar" element={<ArizalarPage />} />
            <Route path="akt" element={<AktPage />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
