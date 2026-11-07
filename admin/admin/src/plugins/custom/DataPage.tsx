import { Alert, Empty, Segmented, Skeleton, Space, Typography } from 'antd';
import { Navigate, useNavigate, useParams } from 'react-router-dom';
import { CrudTable } from '../../components/crud/CrudTable';
import { showValue, toFieldSpec } from '../../components/crud/fromModel';
import { useModels, type ModelEntity } from '../../lib/useModels';

function EntityTable({ entity }: { entity: ModelEntity }) {
  if (entity.pending) {
    return <Alert type="warning" showIcon message={`A(z) ${entity.label} táblája még nincs létrehozva — az ágensnek le kell futtatnia a migrációt.`} />;
  }
  const live = entity.fields.filter((f) => !f.pending);
  return (
    <CrudTable
      key={entity.name}
      resource={entity.name}
      title={entity.label}
      fields={live.map(toFieldSpec)}
      columns={live.map((f) => ({ title: f.label, dataIndex: f.name, render: (v: unknown) => showValue(f, v) }))}
    />
  );
}

/** The instance's own entities: a switch between them, and the chosen one's list and form. */
export function DataPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { models, loading } = useModels();
  if (loading) return <Skeleton active style={{ padding: 24 }} />;
  const { entities } = models;
  if (!entities.length) {
    return (
      <div style={{ padding: 24 }}>
        <Typography.Title level={4}>Saját adatok</Typography.Title>
        <Empty description="Még nincs saját adatmodell. Kérd meg az ágenst: „mostantól az ügyfeleimet is itt kezelném…”" />
      </div>
    );
  }
  const current = entities.find((e) => e.name === id);
  if (!current) return <Navigate to={`/adatok/${entities[0].name}`} replace />;
  return (
    <Space direction="vertical" size="middle" style={{ width: '100%', padding: 24 }}>
      <Typography.Title level={4} style={{ margin: 0 }}>Saját adatok</Typography.Title>
      {entities.length > 1 && (
        <Segmented
          value={current.name}
          onChange={(v) => navigate(`/adatok/${v}`)}
          options={entities.map((e) => ({ label: e.label, value: e.name }))}
        />
      )}
      <EntityTable entity={current} />
    </Space>
  );
}
