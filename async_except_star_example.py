<<<<<<< HEAD
# file: async_except_star_example.py
import asyncio

async def task_success():
    await asyncio.sleep(1)
    return "Completed!"

async def task_fail():
    await asyncio.sleep(0.5)
    raise ValueError("Something went wrong in task_fail")

async def main():
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(task_success())
            tg.create_task(task_fail())
    except* ValueError as ve_group:
        for ve in ve_group.exceptions:
            print(f"Caught ValueError: {ve}")
    except* Exception as e_group:
        for e in e_group.exceptions:
            print(f"Other exception: {e}")

asyncio.run(main())
=======
# file: async_except_star_example.py
import asyncio

async def task_success():
    await asyncio.sleep(1)
    return "Completed!"

async def task_fail():
    await asyncio.sleep(0.5)
    raise ValueError("Something went wrong in task_fail")

async def main():
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(task_success())
            tg.create_task(task_fail())
    except* ValueError as ve_group:
        for ve in ve_group.exceptions:
            print(f"Caught ValueError: {ve}")
    except* Exception as e_group:
        for e in e_group.exceptions:
            print(f"Other exception: {e}")

asyncio.run(main())
>>>>>>> 0c0df91 (Initial push)
