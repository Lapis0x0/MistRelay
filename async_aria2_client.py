import asyncio
import base64
import functools
import json
import os
import uuid
import subprocess
from datetime import datetime
from pprint import pprint
from typing import List, Dict, Any

import aiohttp
import websockets

from configer import ADMIN_ID, UP_TELEGRAM, RPC_URL, RPC_SECRET, FORWARD_ID, UP_ONEDRIVE, RCLONE_REMOTE, RCLONE_PATH
from util import get_file_name, imgCoverFromFile, progress, byte2_readable, hum_convert


# logging.basicConfig(
#     format="%(asctime)s %(message)s",
#     level=logging.DEBUG,
# )


class AsyncAria2Client:
    def __init__(self, rpc_secret, ws_url, bot=None):
        self.rpc_secret = rpc_secret
        self.ws_url = ws_url
        self.websocket = None
        self.reconnect = True
        self.bot = bot
        self.progress_cache = {}

    async def connect(self):
        try:
            self.websocket = await websockets.connect(self.ws_url, ping_interval=30)
            print("WebSocket连接成功")
            asyncio.ensure_future(self.listen())
        except Exception as e:
            print(f"WebSocket连接失败: {e}")
            await self.re_connect()

    async def listen(self):
        try:
            async for message in self.websocket:
                result = json.loads(message)
                if 'id' in result and result['id'] is None:
                    continue
                print(f'rec message:{message}')
                if 'error' in result:
                    err_msg = result['error']['message']
                    err_code = result['error']['code']
                elif 'method' in result:
                    method_name = result['method']
                    if method_name == 'aria2.onDownloadStart':
                        await self.on_download_start(result)
                    elif method_name == 'aria2.onDownloadComplete':
                        await self.on_download_complete(result)
                    elif method_name == 'aria2.onDownloadError':
                        await self.on_download_error(result)
                    elif method_name == 'aria2.onDownloadPause':
                        await self.on_download_pause(result)
        except websockets.exceptions.ConnectionClosedError:
            print("WebSocket连接已关闭")
            await self.re_connect()

    def parse_json_to_str(self, method, params):
        params_ = self.get_rpc_body(method, params)
        return json.dumps(params_)

    def get_rpc_body(self, method, params=[]):
        params_ = {
            'jsonrpc': '2.0',
            'id': str(uuid.uuid4()),
            'method': method,
            'params': [f'token:{self.rpc_secret}'] + params
        }
        return params_

    async def add_uri(self, uris: List[str], options: Dict[str, Any] = None):
        params = [uris]
        if options:
            params.append(options)

        rpc_body = self.get_rpc_body('aria2.addUri', params)
        print(rpc_body)
        return await self.post_body(rpc_body)

    async def add_torrent(self, path, options=None, position: int = None):
        with open(path, "rb") as file:
            # 读取文件内容
            file_content = file.read()
            base64_content = str(base64.b64encode(file_content), "utf-8")
        params = [
            base64_content
        ]
        if options:
            params.append(options)
        if position is not None:
            params.append(position)
        else:
            params.append([999])

        rpc_body = self.get_rpc_body('aria2.addTorrent', params)
        return await self.post_body(rpc_body)

    async def tell_status(self, gid):
        params = [gid]
        rpc_body = self.get_rpc_body('aria2.tellStatus', params)
        data = await self.post_body(rpc_body)
        return data['result']

    async def post_body(self, rpc_body):
        async with aiohttp.ClientSession() as session:
            async with session.post(f'http://{RPC_URL}', json=rpc_body) as response:
                return await response.json()

    async def re_connect(self):
        if self.reconnect:
            print("等待5秒后尝试重新连接...")
            await asyncio.sleep(5)
            await self.connect()
        else:
            print("已禁用重新连接功能")

    async def on_download_start(self, result):
        gid = result['params'][0]['gid']
        print(f"===========下载 开始 任务id:{gid}")
        tellStatus = await self.tell_status(gid)
        file_name = get_file_name(tellStatus)
        dir = tellStatus["dir"]
        if self.bot:
            msg = await self.bot.send_message(ADMIN_ID,
                                              f'{file_name} 任务已经开始下载... \n 对应路径: {dir}',
                                              parse_mode='html')
            asyncio.create_task(self.check_download_progress(gid, msg))
            print('轮训进度')

    async def check_download_progress(self, gid, msg):
        try:
            while True:
                task = await self.tell_status(gid)
                completedLength = task['completedLength']
                totalLength = task['totalLength']
                downloadSpeed = task['downloadSpeed']
                status = task['status']
                file_name = get_file_name(task)
                if file_name == '':
                    continue
                size = byte2_readable(int(totalLength))
                speed = hum_convert(int(downloadSpeed))
                prog = progress(int(totalLength), int(completedLength))
                if status != 'complete':
                    msg = await self.bot.edit_message(msg,
                                                      f'{file_name} 下载中... \n '
                                                      f'对应路径: {dir}\n'
                                                      f'进度: {prog}\n'
                                                      f'大小: {size}\n'
                                                      f'速度: {speed}/s\n'
                                                      f'时间：{datetime.now()}',
                                                      parse_mode='html')
                    await asyncio.sleep(3)
                else:
                    return

        except Exception as e:
            print('任务取消111')
            print(e)

    async def on_download_complete(self, result):
        gid = result['params'][0]['gid']
        print(f"===========下载 完成 任务id:{gid}")
        tellStatus = await self.tell_status(gid)
        files = tellStatus['files']
        for file in files:
            path = file['path']
            if self.bot:
                await self.bot.send_message(ADMIN_ID,
                                            '下载完成====> ' + path,
                                            )
                # 处理元数据文件
                if '[METADATA]' in path:
                    os.unlink(path)
                    return
                
                # 根据配置选择上传方式
                if UP_ONEDRIVE:
                    # 使用rclone上传到OneDrive
                    await self.upload_to_onedrive(path)
                elif UP_TELEGRAM:
                    # 上传到Telegram的原有逻辑
                    try:
                        # 检查文件是否为图片
                        if path.endswith(('.jpg', '.jpeg', '.png', '.gif')):
                            msg = await self.bot.send_message(ADMIN_ID, path + ' \n上传中 : 0%')
                            partial_callback = functools.partial(self.callback, gid=gid, msg=msg, path=path)
                            temp_msg = await self.bot.send_file(ADMIN_ID,
                                                                path,
                                                                progress_callback=partial_callback
                                                                )
                            if FORWARD_ID:
                                await temp_msg.forward_to(int(FORWARD_ID))

                            await msg.delete()
                        # 检查文件是否为视频
                        elif path.endswith(('.mp4', '.mkv', '.avi', '.mov')):
                            pat = os.path.dirname(path)
                            filename = os.path.basename(path).split('.')[0]
                            # 生成视频封面
                            imgCoverFromFile(path, pat + '/' + filename + '.jpg')
                            msg = await self.bot.send_message(ADMIN_ID, path + ' \n上传中 : 0%')
                            partial_callback = functools.partial(self.callback, gid=gid, msg=msg, path=path)
                            temp_msg = await self.bot.send_file(ADMIN_ID,
                                                                path,
                                                                thumb=pat + '/' + filename + '.jpg',
                                                                progress_callback=partial_callback
                                                                )
                            if FORWARD_ID:
                                await temp_msg.forward_to(int(FORWARD_ID))

                            await msg.delete()
                            os.unlink(pat + '/' + filename + '.jpg')
                            os.unlink(path)
                        else:
                            msg = await self.bot.send_message(ADMIN_ID, path + ' \n上传中 : 0%')
                            partial_callback = functools.partial(self.callback, gid=gid, msg=msg, path=path)
                            temp_msg = await self.bot.send_file(ADMIN_ID,
                                                                path,
                                                                progress_callback=partial_callback
                                                                )
                            if FORWARD_ID:
                                await temp_msg.forward_to(int(FORWARD_ID))

                            await msg.delete()
                            os.unlink(path)

                    except Exception as e:
                        print(e)
                        await self.bot.send_message(ADMIN_ID, f'{path}不存在，上传失败')

    async def on_download_pause(self, result):
        gid = result['params'][0]['gid']
        print(f"===========下载 暂停 任务id:{gid}")
        tellStatus = await self.tell_status(gid)
        filename = get_file_name(tellStatus)
        if self.bot:
            await self.bot.send_message(ADMIN_ID, f'{filename} 任务已经成功暂停')

    async def on_download_error(self, result):
        gid = result['params'][0]['gid']
        tellStatus = await self.tell_status(gid)
        errorCode = tellStatus['errorCode']
        errorMessage = tellStatus['errorMessage']
        print(f'===========下载 错误 任务id:{gid} 错误码: {errorCode} 错误信息{errorMessage}')
        if self.bot:
            if errorCode == '12':
                await self.bot.send_message(ADMIN_ID, '任务已经在下载,可以删除任务后重新添加')
            else:
                await self.bot.send_message(ADMIN_ID, errorMessage)

    async def tell_stopped(self, offset: int, num: int):
        params = [
            offset, num
        ]
        rpc_body = self.get_rpc_body('aria2.tellStopped', params)
        data = await self.post_body(rpc_body)
        return data['result']

    async def tell_waiting(self, offset: int, num: int):
        params = [
            offset, num
        ]
        rpc_body = self.get_rpc_body('aria2.tellWaiting', params)
        data = await self.post_body(rpc_body)
        return data['result']

    async def tell_active(self):
        params = []
        rpc_body = self.get_rpc_body('aria2.tellActive', params)
        data = await self.post_body(rpc_body)
        return data['result']

    async def pause(self, gid: str):
        params = [gid]
        jsonreq = self.parse_json_to_str('aria2.pause', params)
        print(jsonreq)
        await self.websocket.send(jsonreq)

    async def unpause(self, gid: str):
        params = [gid]
        jsonreq = self.parse_json_to_str('aria2.unpause', params)
        print(jsonreq)
        await self.websocket.send(jsonreq)

    async def remove(self, gid: str):
        params = [gid]
        rpc_body = self.get_rpc_body('aria2.remove', params)
        data = await self.post_body(rpc_body)
        return data

    async def remove_download_result(self, gid: str):
        params = [gid]
        jsonreq = self.parse_json_to_str('aria2.removeDownloadResult', params)
        print(jsonreq)
        await self.websocket.send(jsonreq)

    async def change_global_option(self, params):
        rpc_body = self.get_rpc_body('aria2.changeGlobalOption', params)
        return await self.post_body(rpc_body)

    async def get_global_option(self):
        rpc_body = self.get_rpc_body('aria2.getGlobalOption')
        data = await self.post_body(rpc_body)
        return data['result']

    async def upload_to_onedrive(self, file_path):
        """
        使用rclone将文件上传到OneDrive
        """
        try:
            if not os.path.exists(file_path):
                print(f"文件不存在: {file_path}")
                if self.bot:
                    await self.bot.send_message(ADMIN_ID, f'文件不存在，无法上传到OneDrive: {file_path}')
                return False
                
            # 构建rclone命令
            remote_path = f"{RCLONE_REMOTE}:{RCLONE_PATH}"
            command = ["rclone", "copy", file_path, remote_path, "-P"]
            
            # 通知开始上传
            if self.bot:
                msg = await self.bot.send_message(ADMIN_ID, f'开始上传到OneDrive: {file_path}')
            
            # 执行rclone命令
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            
            # 读取输出并更新进度
            last_progress = ""
            for line in process.stdout:
                if "Transferred:" in line and self.bot:
                    # 提取进度信息
                    progress_info = line.strip()
                    if progress_info != last_progress:
                        last_progress = progress_info
                        # 每5行更新一次消息，避免频繁更新
                        if hash(progress_info) % 5 == 0:
                            await self.bot.edit_message(msg, f'上传到OneDrive: {file_path}\n{progress_info}')
            
            # 等待进程完成
            process.wait()
            
            # 检查上传是否成功
            if process.returncode == 0:
                if self.bot:
                    await self.bot.edit_message(msg, f'成功上传到OneDrive: {file_path}')
                return True
            else:
                if self.bot:
                    await self.bot.edit_message(msg, f'上传到OneDrive失败: {file_path}')
                return False
                
        except Exception as e:
            print(f"上传到OneDrive时出错: {e}")
            if self.bot:
                await self.bot.send_message(ADMIN_ID, f'上传到OneDrive时出错: {e}')
            return False

    async def callback(self, current, total, gid, msg=None, path=None):
        """
        上传进度回调函数
        """
        if not msg or not path:
            return
            
        gid_progress = self.progress_cache.get(gid, 0)
        new_progress = current / total
        formatted_progress = "{:.2%}".format(new_progress)
        if abs(new_progress - gid_progress) >= 0.05:
            self.progress_cache[gid] = new_progress
            try:
                await self.bot.edit_message(msg, path + f' \n上传中 : {formatted_progress}')
            except Exception as e:
                print(f"更新进度消息失败: {e}")


async def main():
    client = AsyncAria2Client(RPC_SECRET, f'ws://{RPC_URL}', None)

    await client.connect()
    result = await client.get_global_option()
    pprint(result)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    try:
        loop.create_task(main())
        loop.run_forever()
    except KeyboardInterrupt:
        pass
