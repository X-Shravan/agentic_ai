import { AlertPanel } from '../components/AlertPanel';
import { CameraGrid } from '../components/CameraGrid';
import { RiskHeatmap } from '../components/RiskHeatmap';
import { Navbar } from '../components/Navbar';

export default function DashboardPage() {
  return <><Navbar /><main className="space-y-6 p-6"><CameraGrid /><RiskHeatmap /><AlertPanel /></main></>;
}
