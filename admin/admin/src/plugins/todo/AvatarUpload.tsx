import { useState } from 'react';
import { Alert, Avatar, Button, Space, Upload } from 'antd';
import { UploadOutlined } from '@ant-design/icons';
export function AvatarUpload({ value, onChange }: { value?: string; onChange?: (value: string) => void }) {
  const [error, setError] = useState('');
  return <Space direction="vertical">
    <Space><Avatar size={40} src={value} /><Upload accept="image/png,image/jpeg,image/webp,image/gif" showUploadList={false} beforeUpload={file => {
      setError('');
      if (file.size > 64 * 1024) { setError('Ez a kép túl nagy, próbálj kisebbet'); return Upload.LIST_IGNORE; }
      if (!/^image\/(png|jpeg|webp|gif)$/.test(file.type)) { setError('Válassz egy képet.'); return Upload.LIST_IGNORE; }
      const reader = new FileReader();
      reader.onload = () => {
        const data = String(reader.result);
        if (data.length > 65536) setError('Ez a kép túl nagy, próbálj kisebbet');
        else onChange?.(data);
      };
      reader.onerror = () => setError('Nem sikerült beolvasni a képet.');
      reader.readAsDataURL(file);
      return false;
    }}><Button icon={<UploadOutlined />}>Kép kiválasztása</Button></Upload></Space>
    {error && <Alert type="info" message={error} />}
  </Space>;
}
