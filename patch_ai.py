def update_ai_orchestrator():
    with open('src/services/ai_orchestrator.py', 'r', encoding='utf-8') as f:
        content = f.read()

    old_persist = '''                # Increment family quota usage
                family = session.get(Family, user.family_id)
                if family:
                    family.monthly_tx_count += 1
                    session.add(family)
                
                session.commit()
                return tx.id'''

    new_persist = '''                # Increment family quota usage atomically
                from sqlalchemy import update
                session.exec(
                    update(Family)
                    .where(Family.id == user.family_id)
                    .values(monthly_tx_count=Family.monthly_tx_count + 1)
                )
                
                session.commit()
                return tx.id'''

    content = content.replace(old_persist, new_persist)

    old_intent = '''                        elif raw_lower.startswith("/removemember"):
                            target = raw_text[13:].strip()
                            parsed_query = ParsedQueryIntent(intent="remove_member", target_member=target)
                        elif raw_lower.startswith("remove member"):
                            target = raw_text[13:].strip()
                            parsed_query = ParsedQueryIntent(intent="remove_member", target_member=target)'''

    new_intent = '''                        elif raw_lower.startswith("/removemember") or raw_lower.startswith("remove member"):
                            target = raw_text.split(" ", 1)[1].strip() if " " in raw_text else ""
                            parsed_query = ParsedQueryIntent(intent="remove_member", target_member=target)'''

    content = content.replace(old_intent, new_intent)

    old_family_info = '''                    elif intent == "family_info":
                        family_service = FamilyService(self.engine)
                        info = await asyncio.to_thread(family_service.get_family_info, user_uuid)
                        if "error" in info:
                            response_text = info["error"]
                        else:
                            admin_indicator = "👑 " if info['is_current_user_admin'] else ""
                            response_text = f"🏠 <b>{info['name']}</b> {admin_indicator}\\n"
                            
                            response_text += f"\\n<b>Plan:</b> {info['plan_type'].replace('_', ' ').title()}\\n"
                            if info['plan_type'] == 'trial' and info['trial_ends_at']:
                                ends = info['trial_ends_at'].strftime('%b %d, %Y')
                                response_text += f"<i>Trial Ends: {ends}</i>\\n"
                            
                            response_text += f"\\n<b>Usage:</b>\\n"
                            response_text += f"• Transactions This Month: {info['monthly_tx_count']}\\n"
                            if info['plan_type'] == 'free':
                                response_text += f"• Limit: 30\\n"
                                
                            response_text += f"\\n<b>Members ({len(info['members'])}):</b>\\n"
                            for idx, m in enumerate(info['members'], 1):
                                role = " (Admin)" if m['is_admin'] else ""
                                name = m['full_name'] or m['username'] or f"User {m['telegram_id']}"
                                response_text += f"{idx}. {name}{role}\\n"
                                
                            if info['is_current_user_admin']:
                                response_text += f"\\n<i>To remove a member, use /removemember @username</i>"'''

    new_family_info = '''                    elif intent == "family_info":
                        family_service = FamilyService(self.engine)
                        info = await asyncio.to_thread(family_service.get_family_info, user_uuid)
                        if "error" in info:
                            response_text = info["error"]
                        elif not info.get("is_current_user_admin"):
                            response_text = "⚠️ Only the family admin can list members and view detailed family info."
                        else:
                            admin_indicator = "👑 " if info['is_current_user_admin'] else ""
                            response_text = f"🏠 <b>{info['name']}</b> {admin_indicator}\\n"
                            
                            response_text += f"\\n<b>Plan:</b> {info['plan_type'].replace('_', ' ').title()}\\n"
                            if info['plan_type'] == 'trial' and info['trial_ends_at']:
                                ends = info['trial_ends_at'].strftime('%b %d, %Y')
                                response_text += f"<i>Trial Ends: {ends}</i>\\n"
                            
                            response_text += f"\\n<b>Usage:</b>\\n"
                            response_text += f"• Transactions This Month: {info['monthly_tx_count']}\\n"
                            if info['plan_type'] == 'free':
                                response_text += f"• Limit: 30\\n"
                                
                            response_text += f"\\n<b>Members ({len(info['members'])}):</b>\\n"
                            for idx, m in enumerate(info['members'], 1):
                                role = " (Admin)" if m['is_admin'] else ""
                                name = m['full_name'] or m['username'] or f"User {m['telegram_id']}"
                                response_text += f"{idx}. {name}{role}\\n"
                                
                            if info['is_current_user_admin']:
                                response_text += f"\\n<i>To remove a member, use /removemember @username</i>"'''

    content = content.replace(old_family_info, new_family_info)

    old_create_family = '''                    elif intent == "create_family":
                        # Attempt to create a new family grouping and invite link
                        family_service = FamilyService(self.engine)
                        result = await asyncio.to_thread(
                            family_service.create_family,
                            user_uuid,
                            f"{text} Family" if text else None
                        )
                        if result:
                            # Generate an invite token immediately
                            invite = await asyncio.to_thread(
                                family_service.create_invite,
                                user_uuid,
                                expires_in_days=7
                            )
                            if invite:
                                response_text = (
                                    f"🏠 <b>Family Workspace Created!</b>\\n\\n"
                                    f"Invite your partner or family member using this link:\\n"
                                    f"<code>https://t.me/ClanomyBot?start=join_{invite.token}</code>\\n\\n"
                                    f"This link expires in 7 days."
                                )
                            else:
                                response_text = "Family created, but failed to generate invite link."
                        else:
                            response_text = "Failed to create family."'''
    new_create_family = '''                    elif intent == "create_family":
                        # Attempt to create a new family grouping and invite link
                        family_service = FamilyService(self.engine)
                        # We need to know if user had trial before calling create_family? create_family checks it itself.
                        # Let's get user before to check trial
                        with Session(self.engine) as session:
                            u = session.get(User, user_uuid)
                            had_trial = u.has_used_trial if u else False
                            
                        result = await asyncio.to_thread(
                            family_service.create_family,
                            user_uuid,
                            f"{text} Family" if text else None
                        )
                        if result:
                            # Generate an invite token immediately
                            invite = await asyncio.to_thread(
                                family_service.create_invite,
                                user_uuid,
                                expires_in_days=7
                            )
                            if invite:
                                response_text = (
                                    f"🏠 <b>Family Workspace Created!</b>\\n\\n"
                                    f"Invite your partner or family member using this link:\\n"
                                    f"<code>https://t.me/ClanomyBot?start=join_{invite.token}</code>\\n\\n"
                                    f"This link expires in 7 days."
                                )
                                if had_trial:
                                    response_text += "\\n\\n<i>Your trial was already consumed, so this workspace starts on the Free plan.</i>"
                            else:
                                response_text = "Family created, but failed to generate invite link."
                        else:
                            response_text = "Failed to create family."'''
    
    content = content.replace(old_create_family, new_create_family)

    with open('src/services/ai_orchestrator.py', 'w', encoding='utf-8') as f:
        f.write(content)

update_ai_orchestrator()
