# django-activity-signup

这是为一个基于QQ群组织的虚拟航司无偿开发的活动报名网站，项目基于 Django 开发，提供活动发布与报名功能。

---

## 如何改成你自己的版本

| 路径                                    | 修改内容                             |
|---------------------------------------|--------------------------------------|
| `activityui/static/images/background.*` | JPG 和 WEBP 格式的登录页背景图片         |
| `activityui/static/images/logo.*`       | JPG 和 WEBP 格式的登录页 Logo 图标      |
| `activityui/admin.py`                   | 13–15 行修改管理后台标题和页面显示信息    |
| `activity_signup/settings.py`           | 搜索关键词 `PLACEHOLDER` 并替换成你自己的值（**必须！**） |

**你必须设置settings.py中有关Turnstile的内容，否则无法从前端完成注册和登录**

---

## 本地运行

```bash
pip install -r requirements.txt
python3 manage.py migrate
python3 manage.py createsuperuser  # 创建管理员账户
python3 manage.py runserver
````

关于生产部署、数据库配置等更详细的内容，请参考 [Django 文档](https://docs.djangoproject.com/)。
