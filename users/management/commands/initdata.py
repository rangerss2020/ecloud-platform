from django.core.management.base import BaseCommand
from users.models import User
from apimodels.models import Channel, ApiModel, ApiParameter, Capability
from agent.models import AgentProfile
from billing.models import PricingRule


class Command(BaseCommand):
    help = '初始化平台数据'

    def handle(self, *args, **options):
        self.stdout.write('Starting initialization...\n')

        if not User.objects.filter(username='admin').exists():
            admin = User.objects.create_superuser(
                username='admin', password='admin123', email='admin@ecloud.com',
                role='admin', balance=99999, phone='13800000001'
            )
            self.stdout.write('Admin: admin / admin123')
        else:
            self.stdout.write('Admin exists, skip')

        if not User.objects.filter(username='agent01').exists():
            agent = User.objects.create_user(
                username='agent01', password='agent123', email='agent01@ecloud.com',
                role='agent', balance=5000, phone='13800000002'
            )
            AgentProfile.objects.create(user=agent, level=1, commission_rate=15)
            self.stdout.write('Agent: agent01 / agent123 (15%)')
        else:
            self.stdout.write('Agent exists, skip')

        if not User.objects.filter(username='member01').exists():
            member = User.objects.create_user(
                username='member01', password='member123', email='member01@ecloud.com',
                role='member', balance=500, phone='13800000003'
            )
            self.stdout.write('Member: member01 / member123')
        else:
            self.stdout.write('Member exists, skip')

        ch, ch_created = Channel.objects.get_or_create(
            code='maas',
            defaults={
                'name': '移动云MaaS',
                'description': '移动云大模型服务平台',
                'base_url': 'https://zhenze-huhehaote.cmecloud.cn',
                'auth_type': 'bearer',
                'api_key': 'YOUR_MAAS_API_KEY',
                'status': 'enabled',
                'sort_order': 1,
            }
        )
        self.stdout.write(f'Channel: {ch.name} [{ch.get_auth_type_display()}]')

        sh, _ = Channel.objects.get_or_create(
            code='seedance',
            defaults={
                'name': 'Seedance视频',
                'description': '豆包 Seedance 2.0 视频生成服务',
                'base_url': 'https://zhenze-huhehaote.cmecloud.cn/api/v3',
                'auth_type': 'bearer',
                'api_key': 'YOUR_SEEDANCE_API_KEY',
                'status': 'enabled',
                'sort_order': 2,
            }
        )
        self.stdout.write(f'Channel: {sh.name} [{sh.get_auth_type_display()}]')

        capabilities = [
            ('image_input', '图片输入', ''),
            ('video_input', '视频输入', ''),
            ('audio_input', '音频输入', ''),
            ('image_output', '图片输出', ''),
            ('video_output', '视频输出', ''),
            ('audio_output', '音频输出', ''),
            ('reasoning', '深度思考', ''),
        ]
        cap_objs = {}
        for code, name, icon in capabilities:
            obj, _ = Capability.objects.get_or_create(code=code, defaults={'name': name, 'icon': icon, 'sort_order': len(cap_objs)})
            cap_objs[code] = obj
            self.stdout.write(f'  Cap: {name}')

        models_data = [
            {'code':'deepseek-v4-pro','name':'DeepSeek-V4-Pro','bill_type':'per_unit','unit_type':'per_1m','price':0.02,'servlet_path':'/v1/chat/completions','params':[{'n':'model','t':'string','r':True,'d':'deepseek-v4-pro'}]},
            {'code':'deepseek-v4-flash','name':'DeepSeek-V4-Flash','bill_type':'per_unit','unit_type':'per_1m','price':0.01,'servlet_path':'/v1/chat/completions','params':[{'n':'model','t':'string','r':True,'d':'deepseek-v4-flash'}]},
            {'code':'deepseek-v3.2','name':'DeepSeek-V3.2','bill_type':'per_unit','unit_type':'per_1m','price':0.008,'servlet_path':'/v1/chat/completions','params':[{'n':'model','t':'string','r':True,'d':'deepseek-v3.2'}]},
            {'code':'deepseek-v3.1','name':'DeepSeek-V3.1','bill_type':'per_unit','unit_type':'per_1m','price':0.006,'servlet_path':'/v1/chat/completions','params':[{'n':'model','t':'string','r':True,'d':'deepseek-v3.1'}]},
            {'code':'deepseek-v3','name':'DeepSeek-V3','bill_type':'per_unit','unit_type':'per_1m','price':0.004,'servlet_path':'/v1/chat/completions','params':[{'n':'model','t':'string','r':True,'d':'deepseek-v3'}]},
            {'code':'deepseek-r1','name':'DeepSeek-R1','bill_type':'per_unit','unit_type':'per_1m','price':0.008,'servlet_path':'/v1/chat/completions','params':[{'n':'model','t':'string','r':True,'d':'deepseek-r1'}]},
            {'code':'deepseek-7b','name':'DeepSeek-7B','bill_type':'per_unit','unit_type':'per_1m','price':0.001,'servlet_path':'/v1/chat/completions','params':[{'n':'model','t':'string','r':True,'d':'deepseek-7b'}]},
            {'code':'glm-4.6','name':'GLM-4.6','bill_type':'per_unit','unit_type':'per_1m','price':0.015,'servlet_path':'/v1/chat/completions','params':[{'n':'model','t':'string','r':True,'d':'glm-4-32b-0414'}]},
            {'code':'glm-5','name':'GLM-5','bill_type':'per_unit','unit_type':'per_1m','price':0.02,'servlet_path':'/v1/chat/completions','params':[{'n':'model','t':'string','r':True,'d':'glm-5'}]},
            {'code':'qwen3-235b','name':'Qwen3-235B','bill_type':'per_unit','unit_type':'per_1m','price':0.03,'servlet_path':'/v1/chat/completions','params':[{'n':'model','t':'string','r':True,'d':'qwen3-235b'}]},
            {'code':'qwen3-32b','name':'Qwen3-32B','bill_type':'per_unit','unit_type':'per_1m','price':0.008,'servlet_path':'/v1/chat/completions','params':[{'n':'model','t':'string','r':True,'d':'qwen3-32b'}]},
            {'code':'qwen-vl','name':'Qwen-VL','bill_type':'per_call','unit_type':'','price':0.05,'servlet_path':'/v1/chat/completions','params':[{'n':'model','t':'string','r':True,'d':'qwen-vl'}]},
            {'code':'jiutian-qianyuan','name':'九天-乾元','bill_type':'per_unit','unit_type':'per_1m','price':0.003,'servlet_path':'/v1/chat/completions','params':[{'n':'model','t':'string','r':True,'d':'jiutian-qianyuan'}]},
            {'code':'jiutian-kunyu','name':'九天-坤舆','bill_type':'per_unit','unit_type':'per_1m','price':0.001,'servlet_path':'/v1/chat/completions','params':[{'n':'model','t':'string','r':True,'d':'jiutian-kunyu'}]},
            {'code':'kimi-k2.6','name':'Kimi-K2.6','bill_type':'per_unit','unit_type':'per_1m','price':0.02,'servlet_path':'/v1/chat/completions','params':[{'n':'model','t':'string','r':True,'d':'kimi-k2.6'}]},
            {'code':'llama-3.3','name':'Llama-3.3','bill_type':'per_unit','unit_type':'per_1m','price':0.004,'servlet_path':'/v1/chat/completions','params':[{'n':'model','t':'string','r':True,'d':'llama-3.3'}]},
            {'code':'llama-3.2','name':'Llama-3.2','bill_type':'per_unit','unit_type':'per_1m','price':0.002,'servlet_path':'/v1/chat/completions','params':[{'n':'model','t':'string','r':True,'d':'llama-3.2'}]},
            {'code':'llama-3.1','name':'Llama-3.1','bill_type':'per_unit','unit_type':'per_1m','price':0.002,'servlet_path':'/v1/chat/completions','params':[{'n':'model','t':'string','r':True,'d':'llama-3.1'}]},
            {'code':'hunyuan','name':'混元(腾讯)','bill_type':'per_unit','unit_type':'per_1m','price':0.005,'servlet_path':'/v1/chat/completions','params':[{'n':'model','t':'string','r':True,'d':'hunyuan'}]},
            {'code':'wxyy','name':'文心一言(百度)','bill_type':'per_unit','unit_type':'per_1m','price':0.005,'servlet_path':'/v1/chat/completions','params':[{'n':'model','t':'string','r':True,'d':'wxyy'}]},
            {'code':'embedding','name':'Embedding向量','bill_type':'per_unit','unit_type':'per_1k','price':0.001,'servlet_path':'/v1/embeddings','params':[{'n':'model','t':'string','r':True,'d':'embedding'},{'n':'input','t':'string','r':True,'d':''}]},
            {'code':'doubao-seedance-2.0','name':'Seedance 2.0 视频生成','bill_type':'per_call','unit_type':'','price':5.00,'servlet_path':'/contents/generations/tasks','task_type':'video','channel':'seedance','caps':['image_input','video_input','audio_input','video_output','audio_output'],'resolutions':[{'ratio':'16:9','label':'横屏 16:9','multiplier':1.0},{'ratio':'9:16','label':'竖屏 9:16','multiplier':1.2},{'ratio':'1:1','label':'方形 1:1','multiplier':1.0}],'durations':[{'seconds':5,'label':'5秒','multiplier':0.5},{'seconds':8,'label':'8秒','multiplier':0.8},{'seconds':11,'label':'11秒','multiplier':1.0}],'params':[{'n':'model','t':'string','r':True,'d':'doubao-seedance-2.0'}]},
        ]

        for data in models_data:
            params = data.pop('params', [])
            task_type = data.pop('task_type', 'chat')
            caps_codes = data.pop('caps', [])
            resolutions = data.pop('resolutions', [])
            durations = data.pop('durations', [])
            model_ch = data.pop('channel', 'maas')
            model_channel = ch if model_ch == 'maas' else sh
            code = data.pop('code')
            defaults = {
                'name': data['name'], 'description': data['name'],
                'servlet_path': data['servlet_path'], 'http_method': 'POST',
                'bill_type': data['bill_type'], 'unit_type': data.get('unit_type', ''),
                'price': data['price'], 'status': 'enabled',
                'task_type': task_type,
                'resolution_options': resolutions,
                'duration_options': durations,
            }
            model, created = ApiModel.objects.get_or_create(channel=model_channel, code=code, defaults=defaults)
            if created:
                for i, p in enumerate(params):
                    ApiParameter.objects.create(
                        model=model, param_name=p['n'], param_type=p['t'],
                        required=p['r'], default_value=p.get('d',''),
                        description=p['n'], sort_order=i,
                    )
                for cap_code in caps_codes:
                    c = cap_objs.get(cap_code)
                    if c:
                        model.capabilities.add(c)
                if model.bill_type != 'free' and model.price > 0:
                    PricingRule.objects.get_or_create(
                        api_model=model, bill_type=model.bill_type,
                        defaults={'unit_price': model.price, 'min_level': 1}
                    )
                self.stdout.write(f'  + {model.name}')
            else:
                self.stdout.write(f'  = {model.name}')

        for u in User.objects.filter(api_key=''):
            u.generate_api_keys()
            self.stdout.write(f'  Key: {u.username}')

        sws = [('fuck','replace','****'),('shit','replace','****'),('damn','replace','****')]
        from apigateway.models import SensitiveWord
        for word, level, repl in sws:
            if not SensitiveWord.objects.filter(word=word).exists():
                SensitiveWord.objects.create(word=word, level=level, replacement=repl, category='默认')

        from billing.models import Package
        if Package.objects.count() == 0:
            Package.objects.create(name='体验包', price=9.9, call_limit=100, token_limit=10000, duration_type='day', duration_value=7, description='7天100次调用+1万Token')
            Package.objects.create(name='基础版', price=29.9, call_limit=1000, duration_type='month', duration_value=1, description='月享1000次调用')
            Package.objects.create(name='专业版', price=99, call_limit=5000, token_limit=1000000, duration_type='month', duration_value=1, description='月享5000次调用+100万Token')
            Package.objects.create(name='企业版', price=299, duration_type='year', duration_value=1, description='全年无限调用+无限Token')

        self.stdout.write('\n=== Init complete ===')
        self.stdout.write('Admin:  admin / admin123')
        self.stdout.write('Models: 21 LLM models')
        self.stdout.write('================================')
