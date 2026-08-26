def update_family_service():
    with open('src/services/family_service.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. Update remove_member filtering
    old_remove = '''                # Find member in the family
                all_members = session.exec(select(User).where(User.family_id == family_id)).all()
                target_user = None
                for m in all_members:
                    if (m.username and m.username.lower() == clean_target.lower()) or \\
                       (m.full_name and m.full_name.lower() == clean_target.lower()) or \\
                       str(m.telegram_id) == clean_target or \\
                       str(m.id) == clean_target:
                        target_user = m
                        break'''

    new_remove = '''                # Find member in the family directly via DB
                if clean_target.lower() == "none":
                    self._log_3s_audit("remove_member", start_time)
                    return False, "⚠️ Please specify a valid username or ID.", None, None

                tid = None
                if clean_target.isdigit():
                    tid = int(clean_target)

                from sqlalchemy import or_
                target_user = session.exec(
                    select(User).where(User.family_id == family_id).where(
                        or_(
                            User.username.ilike(clean_target),
                            User.full_name.ilike(clean_target),
                            User.telegram_id == tid if tid is not None else False
                        )
                    )
                ).first()'''

    content = content.replace(old_remove, new_remove)

    old_workspace_remove = '''                # Create new personal workspace for the removed member
                new_family_name = f"{target_user.full_name or target_user.username or 'User'}'s Family"
                plan_type = "free" if target_user.has_used_trial else "trial"
                trial_ends_at = None if target_user.has_used_trial else datetime.now(timezone.utc) + timedelta(days=60)
                
                new_family = Family(
                    name=new_family_name,
                    plan_type=plan_type,
                    trial_ends_at=trial_ends_at
                )
                session.add(new_family)
                session.flush()

                target_user.family_id = new_family.id
                session.add(target_user)

                # Re-assign member's transactions to the new personal workspace
                member_txs = session.exec(select(Transaction).where(Transaction.user_id == target_user.id)).all()
                for tx in member_txs:
                    tx.family_id = new_family.id
                    session.add(tx)

                session.commit()
                session.refresh(target_user)
                session.refresh(new_family)
                self._log_3s_audit("remove_member", start_time)

                target_name = f"@{target_user.username}" if target_user.username else (target_user.full_name or "Member")
                msg = f"🚪 Removed {target_name} from the family workspace. All their personal transactions have been migrated to their new personal workspace."
                return True, msg, target_user, new_family'''

    new_workspace_remove = '''                # Check for existing personal workspace
                active_family_ids = session.exec(select(User.family_id).distinct()).all()
                new_family = session.exec(select(Family).where(Family.id.notin_(active_family_ids))).first()

                had_trial = target_user.has_used_trial
                target_user.has_used_trial = True

                if not new_family:
                    new_family_name = f"{target_user.full_name or target_user.username or 'User'}'s Family"
                    plan_type = "free" if had_trial else "trial"
                    trial_ends_at = None if had_trial else datetime.now(timezone.utc) + timedelta(days=60)
                    new_family = Family(
                        name=new_family_name,
                        plan_type=plan_type,
                        trial_ends_at=trial_ends_at
                    )
                    session.add(new_family)
                    session.flush()
                else:
                    new_family.plan_type = "free" if had_trial else "trial"
                    new_family.trial_ends_at = None if had_trial else datetime.now(timezone.utc) + timedelta(days=60)
                    session.add(new_family)
                    session.flush()

                target_user.family_id = new_family.id
                session.add(target_user)

                from sqlalchemy import update
                session.exec(
                    update(Transaction)
                    .where(Transaction.user_id == target_user.id)
                    .values(family_id=new_family.id)
                )

                session.commit()
                session.refresh(target_user)
                session.refresh(new_family)
                self._log_3s_audit("remove_member", start_time)

                target_name = f"@{target_user.username}" if target_user.username else (target_user.full_name or "Member")
                msg = f"🚪 Removed {target_name} from the family workspace. All their personal transactions have been migrated to their new personal workspace."
                if had_trial:
                    msg += " Their trial was already consumed, so their workspace starts on the Free plan."
                return True, msg, target_user, new_family'''
    
    content = content.replace(old_workspace_remove, new_workspace_remove)

    old_workspace_leave = '''                # Create new personal workspace for leaving member
                new_family_name = f"{user.full_name or user.username or 'User'}'s Family"
                plan_type = "free" if user.has_used_trial else "trial"
                trial_ends_at = None if user.has_used_trial else datetime.now(timezone.utc) + timedelta(days=60)

                new_family = Family(
                    name=new_family_name,
                    plan_type=plan_type,
                    trial_ends_at=trial_ends_at
                )
                session.add(new_family)
                session.flush()

                user.family_id = new_family.id
                session.add(user)

                # Reassign user's transactions
                user_txs = session.exec(select(Transaction).where(Transaction.user_id == user.id)).all()
                for tx in user_txs:
                    tx.family_id = new_family.id
                    session.add(tx)

                session.commit()
                session.refresh(new_family)
                self._log_3s_audit("leave_family", start_time)

                msg = "👋 You have left the family group. You are now in your own personal workspace. All your personal logged transactions have been preserved and moved with you."
                return True, msg, new_family'''

    new_workspace_leave = '''                # Check for existing personal workspace
                active_family_ids = session.exec(select(User.family_id).distinct()).all()
                new_family = session.exec(select(Family).where(Family.id.notin_(active_family_ids))).first()

                had_trial = user.has_used_trial
                user.has_used_trial = True

                if not new_family:
                    new_family_name = f"{user.full_name or user.username or 'User'}'s Family"
                    plan_type = "free" if had_trial else "trial"
                    trial_ends_at = None if had_trial else datetime.now(timezone.utc) + timedelta(days=60)
                    new_family = Family(
                        name=new_family_name,
                        plan_type=plan_type,
                        trial_ends_at=trial_ends_at
                    )
                    session.add(new_family)
                    session.flush()
                else:
                    new_family.plan_type = "free" if had_trial else "trial"
                    new_family.trial_ends_at = None if had_trial else datetime.now(timezone.utc) + timedelta(days=60)
                    session.add(new_family)
                    session.flush()

                user.family_id = new_family.id
                session.add(user)

                from sqlalchemy import update
                session.exec(
                    update(Transaction)
                    .where(Transaction.user_id == user.id)
                    .values(family_id=new_family.id)
                )

                session.commit()
                session.refresh(new_family)
                self._log_3s_audit("leave_family", start_time)

                msg = "👋 You have left the family group. You are now in your own personal workspace. All your personal logged transactions have been preserved and moved with you."
                if had_trial:
                    msg += " Your trial was already consumed, so this workspace starts on the Free plan."
                return True, msg, new_family'''

    content = content.replace(old_workspace_leave, new_workspace_leave)

    with open('src/services/family_service.py', 'w', encoding='utf-8') as f:
        f.write(content)

update_family_service()
