#!/usr/bin/env tarantool
box.cfg{

}

local function bootstrap()
    local space = box.schema.create_space('example')
    space:create_index('primary')
    -- ��������������� ���, ���� ��� ����� �������������� �������� ������� (��� ����, ����� ����� ����� ������ �� �����)
    box.schema.user.grant('guest', 'read,write,execute', 'universe')

    -- Keep things safe by default
    --  box.schema.user.create('example', { password = 'secret' })
    --  box.schema.user.grant('example', 'replication')
    --  box.schema.user.grant('example', 'read,write,execute', 'space', 'example')
end

-- ��� ������� ������� ������� ������������ � �������� ������������� ������
box.once('example-1.0', bootstrap)